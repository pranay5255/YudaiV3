#!/bin/bash

# Yudaiv3 Deployment Script for Vultr
# This script automates the deployment process

set -e  # Exit on any error

echo "🚀 Starting Yudaiv3 deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as the yudai user."
   exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found. Please create it from .env.example"
    exit 1
fi

# Load environment variables
source .env

print_status "Environment loaded successfully"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p ssl
mkdir -p logs
mkdir -p backups

# Check if SSL certificates exist
if [ ! -f ssl/fullchain.pem ] || [ ! -f ssl/privkey.pem ]; then
    print_warning "SSL certificates not found. Please run SSL setup first:"
    echo "sudo certbot certonly --standalone -d yudai.app -d www.yudai.app"
    echo "sudo cp /etc/letsencrypt/live/yudai.app/fullchain.pem /home/yudai/YudaiV3/ssl/"
    echo "sudo cp /etc/letsencrypt/live/yudai.app/privkey.pem /home/yudai/YudaiV3/ssl/"
    echo "sudo chown -R yudai:yudai /home/yudai/YudaiV3/ssl/"
    echo "sudo chmod 600 ssl/*"
    exit 1
fi

print_status "SSL certificates found"

# Stop existing containers
print_status "Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down || true

# Remove old images to ensure fresh build
print_status "Removing old images..."
docker system prune -f

# Build and start services
print_status "Building and starting services..."
docker-compose -f docker-compose.prod.yml up -d --build

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 30

# Check service status
print_status "Checking service status..."
docker-compose -f docker-compose.prod.yml ps

# Check if services are responding
print_status "Testing service health..."

# Test nginx
if curl -f http://localhost/health > /dev/null 2>&1; then
    print_status "✅ Nginx is healthy"
else
    print_error "❌ Nginx health check failed"
fi

# Test backend
if curl -f http://localhost/api/health > /dev/null 2>&1; then
    print_status "✅ Backend API is healthy"
else
    print_error "❌ Backend API health check failed"
fi

# Test SSL
if curl -I https://yudai.app > /dev/null 2>&1; then
    print_status "✅ SSL certificate is working"
else
    print_warning "⚠️  SSL certificate test failed (DNS might not be propagated yet)"
fi

# Test DNS resolution
print_status "Testing DNS resolution..."
if nslookup yudai.app | grep -q "YOUR_VULTR_SERVER_IP"; then
    print_status "✅ DNS is pointing to correct server"
else
    print_warning "⚠️  DNS might not be pointing to correct server"
    print_warning "Please check GoDaddy DNS settings and ensure yudai.app points to your Vultr IP"
fi

# Show logs
print_status "Recent logs:"
docker-compose -f docker-compose.prod.yml logs --tail=20

print_status "🎉 Deployment completed!"
print_status "Your application should be available at: https://yudai.app"
print_status "To view logs: docker-compose -f docker-compose.prod.yml logs -f"
print_status "To restart: docker-compose -f docker-compose.prod.yml restart"
print_status "To update: git pull && ./deploy.sh"