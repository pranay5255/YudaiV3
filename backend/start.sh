#!/bin/bash
set -e

echo "🚀 Starting YudaiV3 Backend..."

# Wait for database to be fully ready before initialization
echo "⏳ Waiting for database to be fully ready..."
max_attempts=60
attempt=0

# Extract database name from DATABASE_URL if POSTGRES_DB is not set
if [ -z "$POSTGRES_DB" ] && [ -n "$DATABASE_URL" ]; then
    # Extract database name from DATABASE_URL (format: postgresql://user:pass@host:port/dbname)
    POSTGRES_DB=$(echo $DATABASE_URL | sed -E 's/.*\/([^\/\?]+)(\?.*)?$/\1/')
    echo "ℹ️ Extracted database name from DATABASE_URL: $POSTGRES_DB"
fi

# Default to 'postgres' if still not set
if [ -z "$POSTGRES_DB" ]; then
    POSTGRES_DB="postgres"
    echo "ℹ️ Using default database name: $POSTGRES_DB"
fi

while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    echo "  Attempt $attempt/$max_attempts..."
    
    # Test database connectivity and readiness
    if pg_isready -h db -p 5432 -U yudai_user -d "$POSTGRES_DB" >/dev/null 2>&1; then
        echo "🎉 Database is ready!"
        break
    else
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts"
            exit 1
        fi
        echo "  ⏳ Waiting 5 seconds before retry..."
        sleep 5
    fi
done

# Initialize database tables
echo "🏗️  Initializing database tables..."
if python db/init_db.py --full-init; then
    echo "✅ Database tables initialized successfully!"
else
    echo "❌ Failed to initialize database tables"
    echo " This is a critical error. Application cannot start without database tables."
    exit 1
fi

# Function to test database connectivity
test_database_connection() {
    echo "🔍 Testing database connectivity..."
    
    # Test 1: Check if we can reach the database host
    echo "  - Testing network connectivity to db:5432..."
    if nc -z db 5432 2>/dev/null; then
        echo "    ✓ Network connectivity OK"
    else
        echo "    ✗ Cannot reach db:5432"
        return 1
    fi
    
    # Test 2: Check if PostgreSQL is ready
    echo "  - Testing PostgreSQL readiness..."
    if pg_isready -h db -p 5432 -U yudai_user -d "$POSTGRES_DB" >/dev/null 2>&1; then
        echo "    ✓ PostgreSQL is ready"
    else
        echo "    ✗ PostgreSQL not ready"
        return 1
    fi

}

# Wait for database with enhanced testing
echo "⏳ Waiting for database to be ready..."
max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    echo "  Attempt $attempt/$max_attempts..."
    
    if test_database_connection; then
        echo "🎉 Database is ready!"
        break
    else
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts"
            echo "🔍 Debugging information:"
            echo "  - DATABASE_URL: $DATABASE_URL"
            echo "  - POSTGRES_DB: $POSTGRES_DB"
            echo "  - Network connectivity:"
            nc -zv db 5432 || echo "    Cannot reach db:5432"
            echo "  - PostgreSQL status:"
            pg_isready -h db -p 5432 -U yudai_user -d "$POSTGRES_DB" || echo "    PostgreSQL not ready"
            exit 1
        fi
        echo "  ⏳ Waiting 5 seconds before retry..."
        sleep 5
    fi
done



echo "🚀 Starting unified YudaiV3 backend server..."
echo "📊 Server will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"

# Start the server
exec python run_server.py
