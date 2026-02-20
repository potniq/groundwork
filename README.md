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
- `GET /requests` public HTML page listing submitted city requests
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

## Generate A City

Use the helper script to trigger `POST /cities` against local API by default:

```bash
./scripts/research_city.sh \
  --city-name "Barcelona"
```

- Defaults to `http://127.0.0.1:8000`
- Reads `ADMIN_API_KEY` from `.env` automatically
- Auto-resolves `country` and `country_code` from city name if omitted
- Override API URL/key with `--api-url` and `--api-key`

Generate a starter set of 30 cities sequentially:

```bash
./scripts/research_cities_batch.sh
```

- Uses a predefined list of 30 major cities
- Calls `./scripts/research_city.sh` one-by-one
- Optionally throttle requests: `--delay-seconds 2`

## Tests

- Unit tests (no DB):
  - `pytest -m unit tests/unit`
- Integration tests (Postgres-backed):
  - `pytest -m integration tests/integration`
- Perplexity responses are mocked with `pytest-httpx`
- Coverage includes city creation/auth, custom slug, city requests flow, and unit helpers

## CircleCI Deploy Flow

- Non-main branches: run `install-deps` -> `test-unit` + `test-integration` + `scan-python-deps`
- `main` branch: run `install-deps` -> `test-unit` + `test-integration` + `scan-python-deps` -> `build-docker` -> `verify-docker` + `scan-docker-image` -> `run-production-migrations` -> `push-docker` -> `deploy-digitalocean`

### Required CircleCI Contexts

`groundwork_docker` context:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_PASSWORD` (Docker Hub access token recommended)
- `DOCKERHUB_REPO` (example: `your-org/groundwork`)

`groundwork_supabase` context:
- `SUPABASE_DB_URL` (direct Postgres connection string for production, percent-encoded if needed)

`groundwork_digitalocean` context:
- `DIGITALOCEAN_ACCESS_TOKEN`
- `DIGITALOCEAN_APP_ID`

`groundwork_snyk` context:
- `SNYK_TOKEN`

### Deployment Notes

- CircleCI pushes two tags to Docker Hub on `main`:
  - `${CIRCLE_SHA1}`
  - `latest`
- Python dependencies are installed in a dedicated `install-deps` job, cached, and persisted to workspace as `.venv` for downstream test/scan jobs.
- CircleCI runs Snyk dependency scanning against `requirements.txt` before Docker build.
- Docker image build and push are split into separate jobs (image is saved/loaded via workspace) to keep deploy sequencing explicit and more reliable.
- CircleCI verifies the built image by starting a container with test env vars and polling `GET /health` until it returns HTTP 200.
- CircleCI runs Snyk container scanning on the built image (`${DOCKERHUB_REPO}:latest`) before migrations/push.
- CircleCI runs production SQL migrations before deploy using:
  - `npx supabase@latest db push --db-url "$SUPABASE_DB_URL" --include-all`
- CircleCI then triggers App Platform deploy using:
  - `doctl apps create-deployment "$DIGITALOCEAN_APP_ID" --wait`
- Runtime app secrets (`DATABASE_URL`, `PERPLEXITY_API_KEY`, `ADMIN_API_KEY`) should be set in DigitalOcean App Platform settings.
