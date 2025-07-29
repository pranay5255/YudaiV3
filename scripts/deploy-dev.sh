#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration for development
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Check if we're in the right directory
if [ ! -f "$COMPOSE_FILE" ]; then
    log_error "Docker Compose file not found: $COMPOSE_FILE"
    exit 1
fi

log_info "Starting development deployment..."

# Build and deploy
log_info "Building and deploying containers..."
docker compose -f $COMPOSE_FILE down
docker compose -f $COMPOSE_FILE build --no-cache
docker compose -f $COMPOSE_FILE up -d

# Wait for services to be ready
log_info "Waiting for services to be ready..."
sleep 30

# Health checks
log_info "Running health checks..."

# Check backend
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    log_success "Backend is healthy"
else
    log_error "Backend health check failed"
    exit 1
fi

# Check database
if docker exec yudai-db pg_isready -U yudai_user -d yudai_db > /dev/null 2>&1; then
    log_success "Database is healthy"
else
    log_error "Database health check failed"
    exit 1
fi

log_success "Development deployment completed successfully!"
log_info "Backend API: http://localhost:8000"
log_info "API Docs: http://localhost:8000/docs" 