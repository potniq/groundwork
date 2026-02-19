#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
for f in supabase/migrations/*.sql; do
    echo "Applying $f..."
    psql "$DATABASE_URL" -f "$f"
done
echo "Migrations complete."
