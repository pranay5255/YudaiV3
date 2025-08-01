#!/bin/bash

# Production deployment script
set -e

echo "🚀 Deploying to Production Environment..."

# Load production environment variables
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
    echo "✅ Loaded production environment variables"
else
    echo "❌ .env.production not found!"
    exit 1
fi

# Stop existing containers
echo "🛑 Stopping existing production containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans

# Build and start production environment
echo "🔨 Building and starting production environment..."
docker compose -f docker-compose.prod.yml up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 15

# Check health
echo "🏥 Checking service health..."
docker compose -f docker-compose.prod.yml ps

echo "✅ Production deployment complete!"
echo "🌐 Production: https://yudai.app"
echo " API: https://api.yudai.app"
echo " API Docs: https://api.yudai.app/docs" 