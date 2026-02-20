#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/research_cities_batch.sh \
    [--api-url "http://127.0.0.1:8000"] \
    [--api-key "<admin-api-key>"] \
    [--delay-seconds 0]

Notes:
- Runs a predefined list of 30 cities sequentially.
- Calls ./scripts/research_city.sh for each city.
- Defaults to local API URL: http://127.0.0.1:8000
- If --api-key is omitted, ADMIN_API_KEY is read from environment/.env
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
CITY_SCRIPT="$ROOT_DIR/scripts/research_city.sh"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

API_URL="${GROUNDWORK_API_URL:-http://127.0.0.1:8000}"
API_KEY="${ADMIN_API_KEY:-}"
DELAY_SECONDS="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --delay-seconds)
      DELAY_SECONDS="${2:-}"
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

if [[ ! -x "$CITY_SCRIPT" ]]; then
  echo "Missing executable script: $CITY_SCRIPT" >&2
  exit 1
fi

if [[ -z "$API_KEY" ]]; then
  echo "Missing API key. Set ADMIN_API_KEY in .env or pass --api-key." >&2
  exit 1
fi

if ! [[ "$DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--delay-seconds must be a non-negative integer." >&2
  exit 1
fi

health_status="$({
  curl -sS -o /dev/null -w "%{http_code}" "$API_URL/health"
} || true)"
if [[ "$health_status" != "200" ]]; then
  echo "API is not reachable at $API_URL (health status: ${health_status:-none})." >&2
  echo "Start the app first, then re-run this script." >&2
  exit 1
fi

# Format: "City|Country"
CITIES=(
  "New York|United States"
  "Los Angeles|United States"
  "Chicago|United States"
  "Toronto|Canada"
  "Vancouver|Canada"
  "Mexico City|Mexico"
  "Sao Paulo|Brazil"
  "Buenos Aires|Argentina"
  "Lima|Peru"
  "Bogota|Colombia"
  "London|United Kingdom"
  "Paris|France"
  "Berlin|Germany"
  "Madrid|Spain"
  "Rome|Italy"
  "Amsterdam|Netherlands"
  "Stockholm|Sweden"
  "Dublin|Ireland"
  "Istanbul|Turkey"
  "Dubai|United Arab Emirates"
  "Tokyo|Japan"
  "Seoul|South Korea"
  "Singapore|Singapore"
  "Bangkok|Thailand"
  "Delhi|India"
  "Sydney|Australia"
  "Melbourne|Australia"
  "Auckland|New Zealand"
  "Cape Town|South Africa"
  "Cairo|Egypt"
)

total="${#CITIES[@]}"
success_count=0
failure_count=0
failed_list=()

for i in "${!CITIES[@]}"; do
  idx="$((i + 1))"
  IFS="|" read -r city_name country <<<"${CITIES[$i]}"
  echo "[$idx/$total] Researching ${city_name}, ${country}..."

  if "$CITY_SCRIPT" \
    --city-name "$city_name" \
    --country "$country" \
    --api-url "$API_URL" \
    --api-key "$API_KEY"; then
    success_count="$((success_count + 1))"
  else
    failure_count="$((failure_count + 1))"
    failed_list+=("${city_name}, ${country}")
  fi

  if [[ "$idx" -lt "$total" && "$DELAY_SECONDS" -gt 0 ]]; then
    sleep "$DELAY_SECONDS"
  fi
done

echo
echo "Batch research complete."
echo "Successful: $success_count"
echo "Failed: $failure_count"

if [[ "$failure_count" -gt 0 ]]; then
  echo "Failures:"
  printf ' - %s\n' "${failed_list[@]}"
  exit 1
fi
