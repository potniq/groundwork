#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/research_city.sh \
    --city-name "Barcelona" \
    [--country "Spain"] \
    [--country-code "ES"] \
    [--latitude 41.3874] \
    [--longitude 2.1686] \
    [--slug "barcelona-es"] \
    [--api-url "http://127.0.0.1:8000"] \
    [--api-key "<admin-api-key>"]

Notes:
- Defaults to local API URL: http://127.0.0.1:8000
- If --api-key is omitted, ADMIN_API_KEY is read from environment/.env
- If country/country-code are omitted, the script auto-resolves them from city name.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

CITY_NAME=""
COUNTRY=""
COUNTRY_CODE=""
LATITUDE=""
LONGITUDE=""
SLUG=""
API_URL="${GROUNDWORK_API_URL:-http://127.0.0.1:8000}"
API_KEY="${ADMIN_API_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --city-name)
      CITY_NAME="${2:-}"
      shift 2
      ;;
    --country)
      COUNTRY="${2:-}"
      shift 2
      ;;
    --country-code)
      COUNTRY_CODE="${2:-}"
      shift 2
      ;;
    --latitude)
      LATITUDE="${2:-}"
      shift 2
      ;;
    --longitude)
      LONGITUDE="${2:-}"
      shift 2
      ;;
    --slug)
      SLUG="${2:-}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CITY_NAME" ]]; then
  echo "Missing required argument: --city-name" >&2
  usage
  exit 1
fi

if [[ -z "$API_KEY" ]]; then
  echo "Missing API key. Set ADMIN_API_KEY in .env or pass --api-key." >&2
  exit 1
fi

export CITY_NAME COUNTRY COUNTRY_CODE LATITUDE LONGITUDE SLUG

NOMINATIM_JSON="[]"
if [[ -z "$COUNTRY" || -z "$COUNTRY_CODE" || -z "$LATITUDE" || -z "$LONGITUDE" ]]; then
  lookup_query="$CITY_NAME"
  if [[ -n "$COUNTRY" ]]; then
    lookup_query="$CITY_NAME, $COUNTRY"
  fi

  export LOOKUP_QUERY="$lookup_query"
  encoded_query="$(python3 - <<'PY'
import os
import urllib.parse

print(urllib.parse.quote_plus(os.environ["LOOKUP_QUERY"]))
PY
)"

  NOMINATIM_URL="https://nominatim.openstreetmap.org/search?q=${encoded_query}&format=jsonv2&addressdetails=1&limit=1"
  NOMINATIM_JSON="$(curl -fsS -A "groundwork-research-city-script/1.0" "$NOMINATIM_URL" || true)"
fi

export NOMINATIM_JSON
payload="$(python3 - <<'PY'
import json
import os

city_name = os.environ["CITY_NAME"].strip()
country = os.environ.get("COUNTRY", "").strip()
country_code = os.environ.get("COUNTRY_CODE", "").strip().upper()
lat = os.environ.get("LATITUDE", "").strip()
lon = os.environ.get("LONGITUDE", "").strip()
slug = os.environ.get("SLUG", "").strip()
results = []
raw_lookup = os.environ.get("NOMINATIM_JSON", "").strip()
if raw_lookup:
    try:
        parsed = json.loads(raw_lookup)
        if isinstance(parsed, list):
            results = parsed
    except json.JSONDecodeError:
        results = []

if not country or not country_code or not lat or not lon:
    resolved = {}
    if results:
        top = results[0]
        address = top.get("address") or {}
        resolved = {
            "country": (address.get("country") or "").strip(),
            "country_code": (address.get("country_code") or "").strip().upper(),
            "latitude": str(top.get("lat") or "").strip(),
            "longitude": str(top.get("lon") or "").strip(),
        }

    country = country or resolved.get("country", "")
    country_code = country_code or resolved.get("country_code", "")
    lat = lat or resolved.get("latitude", "")
    lon = lon or resolved.get("longitude", "")

if not country or not country_code:
    raise SystemExit(
        "Could not determine country/country_code automatically. "
        "Pass --country and --country-code."
    )

payload = {
    "city_name": city_name,
    "country": country,
    "country_code": country_code,
}

if lat:
    payload["latitude"] = float(lat)
if lon:
    payload["longitude"] = float(lon)
if slug:
    payload["slug"] = slug

print(json.dumps(payload))
PY
)"

response_file="$(mktemp)"
status_code="$({
  curl -sS \
    -o "$response_file" \
    -w "%{http_code}" \
    -X POST "$API_URL/cities" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    --data "$payload"
} || true)"

if [[ "$status_code" =~ ^2 ]]; then
  echo "City research started/completed successfully."
else
  echo "Request failed with status $status_code" >&2
fi

if command -v jq >/dev/null 2>&1; then
  jq . "$response_file"
else
  cat "$response_file"
fi

if [[ ! "$status_code" =~ ^2 ]]; then
  rm -f "$response_file"
  exit 1
fi

rm -f "$response_file"
