#!/usr/bin/env bash
set -euo pipefail

if ! command -v supabase >/dev/null 2>&1; then
  echo "Supabase CLI not found. Install it: https://supabase.com/docs/guides/cli" >&2
  exit 1
fi

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 <migration_name>"
  exit 1
fi

supabase migration new "$1"
