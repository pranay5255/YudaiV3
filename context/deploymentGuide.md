# YudaiV3 Production Deployment Guide

This guide will help you deploy YudaiV3 on a Vultr instance with automatic CI/CD deployment using Caddy as a reverse proxy.

## Overview

- **Domain**: yudai.app (GoDaddy)
- **Server**: Vultr instance
- **Reverse Proxy**: Caddy
- **CI/CD**: GitHub Actions with automatic deployment on main branch merges
- **SSL**: Automatic with Caddy

## Prerequisites

- Vultr instance ready (Ubuntu 22.04 LTS recommended)
- Domain yudai.app pointing to your Vultr instance
- GitHub repository with main branch
- SSH access to your Vultr instance

## Step 1: Server Setup

### 1.1 Initial Server Configuration

SSH into your Vultr instance and run these commands:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y curl wget git unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release

# Install Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Create application directory
sudo mkdir -p /opt/yudai
sudo chown $USER:$USER /opt/yudai
```

### 1.2 Configure Firewall

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
sudo ufw --force enable

# Check firewall status
sudo ufw status
```

## Step 2: Domain Configuration

### 2.1 GoDaddy DNS Setup

1. Log into your GoDaddy account
2. Go to DNS Management for yudai.app
3. Add/update these DNS records:

```
Type: A
Name: @
Value: [YOUR_VULTR_IP_ADDRESS]
TTL: 600

Type: A
Name: www
Value: [YOUR_VULTR_IP_ADDRESS]
TTL: 600

Type: CNAME
Name: api
Value: yudai.app
TTL: 600
```

### 2.2 Verify DNS Propagation

```bash
# Check DNS propagation
nslookup yudai.app
dig yudai.app
```

## Step 3: Application Deployment Setup

### 3.1 Create Production Docker Compose

Create `/opt/yudai/docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    build:
      context: ./backend/db
      dockerfile: Dockerfile
    container_name: yudai_db_prod
    restart: unless-stopped
    environment:
      - POSTGRES_DB=yudai_db
      - POSTGRES_USER=yudai_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U yudai_user -d yudai_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Backend API Service
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: yudai_backend_prod
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://yudai_user:${DB_PASSWORD}@db:5432/yudai_db
      - DB_ECHO=false
      - PYTHONPATH=/app
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
      - GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
      - GITHUB_REDIRECT_URI=https://yudai.app/auth/callback
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - /app/__pycache__
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Frontend React Service
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: yudai_frontend_prod
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - VITE_API_URL=https://api.yudai.app
    ports:
      - "127.0.0.1:3000:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - yudai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
    driver: local

networks:
  yudai-network:
    driver: bridge
```

### 3.2 Create Environment File

Create `/opt/yudai/.env.prod`:

```bash
# Database
DB_PASSWORD=your_secure_database_password_here

# API Keys
OPENROUTER_API_KEY=your_openrouter_api_key_here
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here

# Application
NODE_ENV=production
```

### 3.3 Create Deployment Scripts

Create `/opt/yudai/deploy.sh`:

```bash
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

# Configuration
APP_DIR="/opt/yudai"
COMPOSE_FILE="$APP_DIR/docker-compose.prod.yml"
ENV_FILE="$APP_DIR/.env.prod"

# Check if we're in the right directory
if [ ! -f "$COMPOSE_FILE" ]; then
    log_error "Docker Compose file not found: $COMPOSE_FILE"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
    exit 1
fi

log_info "Starting deployment..."

# Pull latest changes
log_info "Pulling latest changes..."
cd $APP_DIR
git pull origin main

# Build and deploy
log_info "Building and deploying containers..."
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE down
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE build --no-cache
docker-compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d

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

# Check frontend
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    log_success "Frontend is healthy"
else
    log_error "Frontend health check failed"
    exit 1
fi

# Check database
if docker exec yudai_db_prod pg_isready -U yudai_user -d yudai_db > /dev/null 2>&1; then
    log_success "Database is healthy"
else
    log_error "Database health check failed"
    exit 1
fi

# Reload Caddy
log_info "Reloading Caddy..."
sudo systemctl reload caddy

log_success "Deployment completed successfully!"
log_info "Frontend: https://yudai.app"
log_info "Backend API: https://api.yudai.app"
log_info "API Docs: https://api.yudai.app/docs"
```

Make it executable:

```bash
chmod +x /opt/yudai/deploy.sh
```

## Step 4: Caddy Reverse Proxy Configuration

### 4.1 Create Caddyfile

Create `/etc/caddy/Caddyfile`:

```
# Main domain - Frontend
yudai.app {
    reverse_proxy localhost:3000 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    
    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.yudai.app https://api.openrouter.ai;"
    }
    
    # Gzip compression
    encode gzip
    
    # Logging
    log {
        output file /var/log/caddy/yudai.app.log
        format json
    }
}

# API subdomain - Backend
api.yudai.app {
    reverse_proxy localhost:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    
    # CORS headers for API
    header {
        Access-Control-Allow-Origin "https://yudai.app"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
        Access-Control-Allow-Credentials true
    }
    
    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
    }
    
    # Gzip compression
    encode gzip
    
    # Logging
    log {
        output file /var/log/caddy/api.yudai.app.log
        format json
    }
}

# Redirect www to non-www
www.yudai.app {
    redir https://yudai.app{uri} permanent
}
```

### 4.2 Create Log Directory

```bash
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy
```

### 4.3 Test and Reload Caddy

```bash
# Test Caddy configuration
sudo caddy validate --config /etc/caddy/Caddyfile

# Reload Caddy
sudo systemctl reload caddy

# Check Caddy status
sudo systemctl status caddy
```

## Step 5: GitHub Actions CI/CD Setup

### 5.1 Create Deployment Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Build and test (reuse existing CI)
  test:
    uses: ./.github/workflows/ci.yml
    secrets: inherit

  # Deploy to production
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Deploy to Vultr
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VULTR_HOST }}
          username: ${{ secrets.VULTR_USERNAME }}
          key: ${{ secrets.VULTR_SSH_KEY }}
          port: ${{ secrets.VULTR_PORT }}
          script: |
            cd /opt/yudai
            git pull origin main
            ./deploy.sh
          env:
            GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 5.2 Set Up GitHub Secrets

In your GitHub repository, go to Settings → Secrets and variables → Actions, and add:

- `VULTR_HOST`: Your Vultr instance IP address
- `VULTR_USERNAME`: Your SSH username (usually `root`)
- `VULTR_SSH_KEY`: Your private SSH key
- `VULTR_PORT`: SSH port (usually `22`)

### 5.3 Generate SSH Key for GitHub Actions

On your Vultr instance:

```bash
# Generate SSH key for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions@yudai.app" -f ~/.ssh/github_actions

# Add public key to authorized_keys
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# Display private key (copy this to GitHub secret VULTR_SSH_KEY)
cat ~/.ssh/github_actions
```

## Step 6: Initial Deployment

### 6.1 Clone Repository

```bash
cd /opt
git clone https://github.com/yourusername/YudaiV3.git yudai
cd yudai
```

### 6.2 Set Up Environment

```bash
# Copy environment file
cp .env.prod.example .env.prod

# Edit environment file with your actual values
nano .env.prod
```

### 6.3 First Deployment

```bash
# Run initial deployment
./deploy.sh
```

### 6.4 Verify Deployment

```bash
# Check container status
docker ps

# Check logs
docker-compose -f docker-compose.prod.yml logs

# Test endpoints
curl -f https://yudai.app
curl -f https://api.yudai.app/health
```

## Step 7: Monitoring and Maintenance

### 7.1 Create Monitoring Script

Create `/opt/yudai/monitor.sh`:

```bash
#!/bin/bash

# Simple monitoring script
echo "=== YudaiV3 System Status ==="
echo "Date: $(date)"
echo ""

echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo "=== Service Health ==="
if curl -f https://yudai.app > /dev/null 2>&1; then
    echo "✅ Frontend: OK"
else
    echo "❌ Frontend: DOWN"
fi

if curl -f https://api.yudai.app/health > /dev/null 2>&1; then
    echo "✅ Backend: OK"
else
    echo "❌ Backend: DOWN"
fi

if docker exec yudai_db_prod pg_isready -U yudai_user -d yudai_db > /dev/null 2>&1; then
    echo "✅ Database: OK"
else
    echo "❌ Database: DOWN"
fi

echo ""
echo "=== Caddy Status ==="
sudo systemctl status caddy --no-pager -l
echo ""

echo "=== Disk Usage ==="
df -h /opt/yudai
echo ""

echo "=== Memory Usage ==="
free -h
```

Make it executable:

```bash
chmod +x /opt/yudai/monitor.sh
```

### 7.2 Set Up Log Rotation

Create `/etc/logrotate.d/yudai`:

```
/var/log/caddy/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 caddy caddy
    postrotate
        systemctl reload caddy
    endscript
}
```

### 7.3 Create Backup Script

Create `/opt/yudai/backup.sh`:

```bash
#!/bin/bash

# Backup script
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker exec yudai_db_prod pg_dump -U yudai_user yudai_db > $BACKUP_DIR/db_backup_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz -C /opt yudai

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
```

Make it executable:

```bash
chmod +x /opt/yudai/backup.sh
```

## Step 8: SSL and Security

### 8.1 SSL Certificate (Automatic with Caddy)

Caddy automatically handles SSL certificates. Verify:

```bash
# Check SSL certificate
sudo caddy list-modules
curl -I https://yudai.app
```

### 8.2 Security Hardening

```bash
# Update system regularly
sudo apt update && sudo apt upgrade -y

# Set up automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Configure fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Step 9: Testing the Complete Setup

### 9.1 Test Manual Deployment

```bash
# Test deployment script
cd /opt/yudai
./deploy.sh
```

### 9.2 Test CI/CD Pipeline

1. Make a small change to your code
2. Push to main branch
3. Check GitHub Actions for deployment
4. Verify changes are live at https://yudai.app

### 9.3 Test All Endpoints

```bash
# Test frontend
curl -I https://yudai.app

# Test backend API
curl -I https://api.yudai.app/health
curl https://api.yudai.app/docs

# Test database connectivity
docker exec yudai_db_prod psql -U yudai_user -d yudai_db -c "SELECT version();"
```

## Troubleshooting

### Common Issues

#### 1. SSL Certificate Issues
```bash
# Check Caddy logs
sudo journalctl -u caddy -f

# Manually obtain certificate
sudo caddy run --config /etc/caddy/Caddyfile
```

#### 2. Container Issues
```bash
# Check container logs
docker-compose -f /opt/yudai/docker-compose.prod.yml logs

# Restart containers
docker-compose -f /opt/yudai/docker-compose.prod.yml restart
```

#### 3. DNS Issues
```bash
# Check DNS propagation
nslookup yudai.app
dig yudai.app

# Test local resolution
curl -H "Host: yudai.app" http://localhost
```

#### 4. Deployment Failures
```bash
# Check deployment logs
cd /opt/yudai
./deploy.sh

# Check GitHub Actions logs
# Go to your repository → Actions → Deploy to Production
```

## Maintenance Commands

```bash
# Monitor system
/opt/yudai/monitor.sh

# Backup system
/opt/yudai/backup.sh

# Update application
cd /opt/yudai
git pull origin main
./deploy.sh

# View logs
docker-compose -f /opt/yudai/docker-compose.prod.yml logs -f

# Restart services
sudo systemctl restart caddy
docker-compose -f /opt/yudai/docker-compose.prod.yml restart
```

## Final Verification

After completing all steps, verify:

1. ✅ https://yudai.app loads the frontend
2. ✅ https://api.yudai.app/health returns 200
3. ✅ https://api.yudai.app/docs shows API documentation
4. ✅ SSL certificates are valid
5. ✅ CI/CD pipeline deploys on main branch merges
6. ✅ All containers are healthy
7. ✅ Logs are being written
8. ✅ Backups are working

## Support

- **Logs**: Check `/var/log/caddy/` and Docker logs
- **Monitoring**: Run `/opt/yudai/monitor.sh`
- **Backups**: Run `/opt/yudai/backup.sh`
- **Deployment**: Run `/opt/yudai/deploy.sh`

Your YudaiV3 application is now deployed and will automatically update whenever you merge to the main branch! 🚀

