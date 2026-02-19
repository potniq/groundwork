#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
for f in migrations/*.sql; do
    echo "Applying $f..."
    psql "$DATABASE_URL" -f "$f"
done
echo "Migrations complete."
