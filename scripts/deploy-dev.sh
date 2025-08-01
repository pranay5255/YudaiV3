#!/bin/bash

# Development deployment script
set -e

echo "🚀 Deploying to Development Environment..."

# Load development environment variables
if [ -f .env.development ]; then
    export $(cat .env.development | grep -v '^#' | xargs)
    echo "✅ Loaded development environment variables"
else
    echo "⚠️  .env.development not found, using defaults"
fi

# Stop existing containers
echo "🛑 Stopping existing development containers..."
docker compose -f docker-compose.dev.yml down --remove-orphans

# Build and start development environment
echo "🔨 Building and starting development environment..."
docker compose -f docker-compose.dev.yml up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking service health..."
docker compose -f docker-compose.dev.yml ps

echo "✅ Development deployment complete!"
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs" 