#!/bin/sh
set -e

echo "Preparing database..."
python -c "import asyncio; from src.db.schema import prepare_database; asyncio.run(prepare_database())"

echo "Starting API..."
exec "$@"
