#!/bin/bash
set -e

echo "Waiting for database..."
while ! pg_isready -h db -p 5432 -U yudai_user; do
  echo "Database not ready, waiting..."
  sleep 2
done
echo "Database is ready!"

echo "Initializing database..."
python init_db.py

echo "Starting unified YudaiV3 backend server..."
python run_server.py
