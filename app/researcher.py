import json
import logging
import re
from pathlib import Path

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


def _collect_intel_urls(intel: CityIntel) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add_url(candidate: str | None) -> None:
        if not candidate:
            return
        cleaned = candidate.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        urls.append(cleaned)

    for authority in intel.authorities:
        add_url(authority.website)
        for app in authority.apps:
            add_url(app.ios_url)
            add_url(app.android_url)

    for payment in intel.payment_methods:
        add_url(payment.url)

    for connection in intel.airport_connections:
        add_url(connection.info_url)

    for source in intel.delay_info:
        add_url(source.url)

    return urls


def _is_acceptable_status_code(status_code: int) -> bool:
    if 200 <= status_code < 400:
        return True
    return status_code in {401, 403, 429}


def _check_url(client: httpx.Client, url: str) -> tuple[bool, str | None]:
    try:
        parsed = httpx.URL(url)
    except Exception:  # noqa: BLE001
        return False, "Invalid URL format"

    if parsed.scheme not in {"http", "https"} or not parsed.host:
        return False, "Unsupported URL scheme or missing host"

    for method in ("HEAD", "GET"):
        try:
            response = client.request(method, url)
        except httpx.HTTPError as exc:
            return False, f"{exc.__class__.__name__}: {exc}"

        status_code = response.status_code
        if method == "HEAD" and status_code in {405, 501}:
            continue

        if status_code in {404, 410}:
            return False, f"HTTP {status_code}"
        if _is_acceptable_status_code(status_code):
            return True, None
        return False, f"HTTP {status_code}"

    return False, "No supported HTTP method"


def _validate_intel_urls(intel: CityIntel, timeout_seconds: float) -> dict[str, str]:
    invalid: dict[str, str] = {}
    urls = _collect_intel_urls(intel)
    if not urls:
        return invalid

    with httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": "groundwork-link-verifier/1.0"},
    ) as client:
        for url in urls:
            is_valid, reason = _check_url(client, url)
            if not is_valid:
                invalid[url] = reason or "Unreachable"

    return invalid


def _invalid_urls_retry_prompt(invalid_urls: dict[str, str]) -> str:
    listed = [f"- {url}: {reason}" for url, reason in invalid_urls.items()]
    if len(listed) > 10:
        listed = listed[:10] + [f"- ... and {len(invalid_urls) - 10} more invalid URLs."]

    return (
        "Your previous JSON included invalid or unreachable URLs:\n"
        f"{chr(10).join(listed)}\n"
        "Regenerate the full JSON with corrected links.\n"
        "Use official sources only, keep URL fields real and reachable, and do not invent URLs.\n"
        "If a URL field is nullable and you cannot verify it, set it to null.\n"
        "Every non-null URL must come from verifiable, cited sources you can access now.\n"
        "Return JSON only."
    )


def _system_prompt() -> str:
    return (
        "You are a transport intelligence analyst for business travelers. "
        "Research city transport and return only valid JSON that matches this schema exactly:\n"
        "{"
        '"authorities":[{"name":"string","website":"string","apps":[{"name":"string","ios_url":"string|null","android_url":"string|null"}]}],'
        '"modes":[{"type":"metro|light_rail|bus|tram|train|ferry|monorail|cable_car|funicular|brt|other","operator":"string","notes":"string"}],' 
        '"payment_methods":[{"method":"string","details":"string","url":"string|null"}],'
        '"operating_hours":{"weekday":"string","weekend":"string","night_service":"string|null"},' 
        '"rideshare":[{"provider":"string","available":true,"notes":"string"}],' 
        '"airport_connections":[{"mode":"string","name":"string","duration":"string","cost":"string","info_url":"string|null"}],'
        '"delay_info":[{"source":"string","url":"string"}],'
        '"tips":"string"'
        "}\n"
        "Rules:\n"
        "- Research all transport options in the metropolitan area, not just city proper.\n"
        "- Include regional/suburban services a traveler from city center might use.\n"
        "- Include only authorities a traveler directly interacts with.\n"
        "- Assume the traveler needs English output: write all text fields in English.\n"
        "- For all URL fields, prefer official English-language pages.\n"
        "- If an official URL has an English variant with a '-en' path suffix, use that '-en' URL.\n"
        "- If no English page exists, use the official non-English page instead of inventing URLs.\n"
        "- For each official mobile app, include direct iOS App Store and Android Google Play links.\n"
        "- If payment method names a specific product or pass (for example iAmsterdam City Card), include official URL in payment_methods.url.\n"
        "- For airport_connections.info_url, include an official info/booking/admin URL when verified; otherwise use null.\n"
        "- Costs must be in local currency with symbols where possible.\n"
        "- URLs must be real and current, and not dead links.\n"
        "- Before finalizing, verify each non-null URL is reachable (not HTTP 404/410).\n"
        "- Use only URLs from verifiable, cited sources you can access now.\n"
        "- Never use placeholders (example.com, localhost) or guessed paths.\n"
        "- If a URL field is nullable and you cannot verify it, set it to null.\n"
        "- No markdown. No explanation. JSON only."
    )


def _load_mock_intel() -> CityIntel | None:
    settings = get_settings()
    mock_response_file = settings.PERPLEXITY_MOCK_RESPONSE_FILE
    if not mock_response_file:
        return None

    try:
        payload = json.loads(Path(mock_response_file).read_text(encoding="utf-8"))
        return CityIntel.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Invalid PERPLEXITY_MOCK_RESPONSE_FILE at {mock_response_file}: {exc}") from exc


def generate_intel(city_name: str, country: str) -> CityIntel:
    mock_intel = _load_mock_intel()
    if mock_intel is not None:
        return mock_intel

    settings = get_settings()
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
            intel = CityIntel.model_validate(parsed)
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

        if settings.VERIFY_GENERATED_URLS:
            invalid_urls = _validate_intel_urls(intel, timeout_seconds=settings.URL_VERIFICATION_TIMEOUT_SECONDS)
            if invalid_urls:
                sample = "; ".join(f"{url} ({reason})" for url, reason in list(invalid_urls.items())[:3])
                last_error = ValueError(f"Generated intel contains invalid URLs: {sample}")
                if attempt == 0:
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": _invalid_urls_retry_prompt(invalid_urls)})
                    continue
                break

        return intel

    raise RuntimeError(f"Failed to generate valid city intel after retry: {last_error}")
