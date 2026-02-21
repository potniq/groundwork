# AGENTS Guide (Groundwork)

This file is for human and AI contributors (Claude, Gemini, Codex) so work can continue quickly with minimal repo spelunking.

## What This Repo Does

Groundwork is a FastAPI app that generates city transport intelligence (`CityIntel`) and stores it in Postgres. The intelligence payload is generated in `app/researcher.py` via Perplexity and validated against Pydantic models in `app/models.py`.

## Local Development Prereqs

- Python `3.13`
- Postgres running locally
- Repo virtualenv with dependencies installed (`requirements.txt`)
- `.env` file with at least:
  - `DATABASE_URL`
  - `PERPLEXITY_API_KEY`
  - `ADMIN_API_KEY`

## Local Runbook

1. Create/use virtualenv and install deps.
2. Ensure Postgres is reachable on `DATABASE_URL`.
3. Start app:

```bash
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

4. Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

## Test Runbook

- Unit + integration:

```bash
./.venv/bin/pytest tests/
```

- Integration tests rely on fixture JSON at `tests/fixtures/barcelona.json` through `tests/integration/conftest.py`.

## Perplexity Mocking and Fixtures

### Runtime mock mode

If you set `PERPLEXITY_MOCK_RESPONSE_FILE=/absolute/path/to/fixture.json`, `generate_intel(...)` returns that fixture and **does not** call Perplexity. This is the fastest deterministic mode for local runs and CI smoke checks.

### Test fixture format

Fixtures in `tests/fixtures/*.json` should conform to `CityIntel` schema from `app/models.py`.

Validate fixtures:

```bash
./.venv/bin/python - <<'PY'
import json
from pathlib import Path
from app.models import CityIntel

for p in sorted(Path('tests/fixtures').glob('*.json')):
    CityIntel.model_validate(json.loads(p.read_text(encoding='utf-8')))
    print('OK', p)
PY
```

## Generate Fixture JSON From Perplexity (No DB Storage)

Use this when you want fresh mock payloads without hitting `POST /cities`.

```bash
VERIFY_GENERATED_URLS=false ./.venv/bin/python - <<'PY'
import json
from pathlib import Path
from app.researcher import generate_intel

cities = [
    ("Barcelona", "Spain", "barcelona.json"),
    ("Milan", "Italy", "milan.json"),
    ("New York City", "United States", "new-york-city.json"),
    ("London", "United Kingdom", "london.json"),
    ("Riga", "Latvia", "riga-latvia.json"),
]

out = Path("tests/fixtures")
out.mkdir(parents=True, exist_ok=True)

for city, country, filename in cities:
    intel = generate_intel(city, country)
    (out / filename).write_text(
        json.dumps(intel.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("Wrote", out / filename)
PY
```

Notes:
- `VERIFY_GENERATED_URLS=false` avoids hard failures from transient SSL/URL verification edge cases while still enforcing JSON/schema validation.
- This flow calls Perplexity directly via `app.researcher.generate_intel` and does **not** write to DB.

## Existing Helper Scripts

- `scripts/research_city.sh`: Calls `POST /cities` (does write/update DB city rows).
- `scripts/research_cities_batch.sh`: Batch DB-backed generation for predefined cities.
- `scripts/new_migration.sh` and `scripts/run_migrations.sh`: SQL migration helpers.

## Contributor Expectations

- Keep fixtures deterministic and schema-valid.
- Prefer adding new fixture files over replacing existing ones unless intentionally refreshing.
- If changing fixture shape assumptions, update both tests and this guide.
