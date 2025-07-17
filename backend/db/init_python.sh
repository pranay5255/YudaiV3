#!/bin/bash

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -U $POSTGRES_USER -d $POSTGRES_DB; do
  sleep 2
done
echo "PostgreSQL is ready!"

echo "Running database initialization..."
cd /app
python3 init_db.py --full-init
echo "Database initialization complete!" 