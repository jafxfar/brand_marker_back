#!/bin/sh
set -e

cd /app

echo "Preparing database..."
python -c "import asyncio; from src.db.schema import prepare_database; asyncio.run(prepare_database())"

echo "Alembic versions in image:"
ls -la alembic/versions
alembic current || true

if ! alembic upgrade head; then
  echo "Alembic failed; starting API anyway (schema already ensured)"
  alembic history || true
fi

if [ "${APP_ENV}" = "development" ]; then
  echo "Seeding development accounts..."
  python scripts/seed.py
fi

echo "Starting API..."
exec "$@"
