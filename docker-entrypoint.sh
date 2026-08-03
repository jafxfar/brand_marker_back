#!/bin/sh
set -e

echo "Preparing database..."
python -c "import asyncio; from src.db.schema import prepare_database; asyncio.run(prepare_database())"
alembic upgrade head

if [ "${APP_ENV:-development}" = "development" ]; then
  echo "Seeding development accounts..."
  python scripts/seed.py
fi

echo "Starting API..."
exec "$@"
