# Groundwork by Potniq

City transport intelligence for business travelers. You land in an unfamiliar city, Groundwork tells you what transport exists, how to pay, when it runs, and how to get from the airport.

URL: `groundwork.potniq.com`

## Quick Start

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

# Install/pin Python and deps for this repo
uv python install 3.13
uv venv --python 3.13
uv pip install -r requirements.txt

# Run locally (needs Postgres running)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/groundwork"
export PERPLEXITY_API_KEY="your-key"
export ADMIN_API_KEY="your-secret-admin-key"
uv run uvicorn app.main:app --reload --port 8000

# Run tests
uv run pytest tests/ --junitxml=test-results/results.xml

# Run with Docker
docker build -t groundwork .
docker run -p 8000:8000 --env-file .env groundwork
```

## Stack

- FastAPI + Jinja2 templates (no frontend build step)
- PostgreSQL (city intel stored in JSONB)
- Perplexity Sonar Pro for city transport research
- Docker for runtime/CI
- Supabase CLI migrations
- Python 3.13

## Data Model

### `cities`

- `slug`, `city_name`, `country`, `country_code`
- optional `latitude`, `longitude`, `metro_area_name`
- `status` in `generating | ready | failed`
- `intel` JSONB validated as `CityIntel`

### `city_requests`

- `raw_input`, optional `email`
- `status` in `pending | fulfilled | ignored`
- visitor requests are stored for manual admin review

## API

- `GET /` homepage with search/filter + city request form
- `GET /cities` list ready cities
- `GET /cities/{slug}` city JSON
- `GET /{slug}` city HTML guide
- `POST /cities` admin-only generation endpoint (`X-API-Key`)
- `POST /requests` public city request intake
- `GET /health` healthcheck

### `POST /cities` payload

```json
{
  "city_name": "Barcelona",
  "country": "Spain",
  "country_code": "ES",
  "latitude": 41.3874,
  "longitude": 2.1686,
  "slug": "barcelona-es"
}
```

- If `slug` is omitted, it auto-generates as `slugify("{city_name}-{country_code}")`.
- Perplexity is called synchronously; failed generation sets `status='failed'`.

### `POST /requests` payload

```json
{
  "raw_input": "Joburg",
  "email": "optional@example.com"
}
```

- Inserts into `city_requests` with `status='pending'`.
- No automatic city generation is triggered.

## Migrations

Create a new migration:

```bash
./scripts/new_migration.sh <name>
# or: supabase migration new <name>
```

Apply migrations to a database URL:

```bash
./scripts/run_migrations.sh
# or: supabase db push --db-url "$DATABASE_URL"
```

## Tests

- Tests run against real Postgres
- Perplexity responses are mocked with `pytest-httpx`
- Coverage includes city creation/auth, custom slug, and city requests flow
