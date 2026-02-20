import json
import logging
import re

import httpx

from app.config import get_settings
from app.models import CityIntel

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
logger = logging.getLogger(__name__)


def _extract_json_text(content: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return content.strip()


def _call_perplexity(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-pro",
        "temperature": 0.1,
        "messages": messages,
    }

    with httpx.Client(timeout=60) as client:
        try:
            response = client.post(PERPLEXITY_URL, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            request_id = exc.response.headers.get("x-request-id") or exc.response.headers.get("request-id")
            body = (exc.response.text or "").strip()
            if len(body) > 1000:
                body = f"{body[:1000]}...[truncated]"

            message = f"Perplexity API error {status_code}"
            if request_id:
                message = f"{message} (request_id={request_id})"
            if body:
                message = f"{message}: {body}"

            logger.error(message)
            raise RuntimeError(message) from exc
        except httpx.HTTPError as exc:
            message = f"Perplexity request failed: {exc}"
            logger.exception(message)
            raise RuntimeError(message) from exc

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Perplexity returned no choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = "\n".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Perplexity response content is empty.")

    return content


def _system_prompt() -> str:
    return (
        "You are a transport intelligence analyst for business travelers. "
        "Research city transport and return only valid JSON that matches this schema exactly:\n"
        "{"
        '"authorities":[{"name":"string","website":"string","app":"string|null"}],' 
        '"modes":[{"type":"metro|light_rail|bus|tram|train|ferry|monorail|cable_car|funicular|brt|other","operator":"string","notes":"string"}],' 
        '"payment_methods":[{"method":"string","details":"string"}],' 
        '"operating_hours":{"weekday":"string","weekend":"string","night_service":"string|null"},' 
        '"rideshare":[{"provider":"string","available":true,"notes":"string"}],' 
        '"airport_connections":[{"mode":"string","name":"string","duration":"string","cost":"string"}],' 
        '"delay_info":[{"source":"string","url":"string"}],'
        '"tips":"string"'
        "}\n"
        "Rules:\n"
        "- Research all transport options in the metropolitan area, not just city proper.\n"
        "- Include regional/suburban services a traveler from city center might use.\n"
        "- Include only authorities a traveler directly interacts with.\n"
        "- Costs must be in local currency with symbols where possible.\n"
        "- URLs must be real and current.\n"
        "- No markdown. No explanation. JSON only."
    )


def generate_intel(city_name: str, country: str) -> CityIntel:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": (
                f"Generate transport intelligence JSON for {city_name}, {country}. "
                "Practical guidance for a business traveler staying 2-5 days."
            ),
        },
    ]

    last_error: Exception | None = None

    for attempt in range(2):
        raw_content = _call_perplexity(messages)

        try:
            parsed = json.loads(_extract_json_text(raw_content))
            return CityIntel.model_validate(parsed)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw_content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was invalid JSON or failed schema validation. "
                            f"Error: {exc}. Return corrected JSON only, no markdown."
                        ),
                    }
                )
                continue
            break

    raise RuntimeError(f"Failed to generate valid city intel after retry: {last_error}")
