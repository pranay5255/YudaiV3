# 🚀 YudaiV3 - Development & Production Setup Guide

## 📋 Overview

This guide provides comprehensive setup instructions for both **Development** and **Production** environments of YudaiV3. The environments are **completely separated** with different Docker configurations while sharing the same codebase.

### 🏗️ Architecture

- **Separation of Concerns**: Only configuration changes between environments
- **Zero Code Changes**: Same application code for both environments
- **Environment-Specific**: Dockerfiles, nginx configs, and environment variables
- **Security**: Production hardening vs development accessibility

---

# 🛠️ DEVELOPMENT ENVIRONMENT SETUP

## Quick Development Start

```bash
# 1. Start development environment
docker compose -f docker-compose-dev.yml up -d

# 2. Check health
docker compose -f docker-compose-dev.yml ps

# 3. View logs
docker compose -f docker-compose-dev.yml logs -f

# 4. Stop when done
docker compose -f docker-compose-dev.yml down
```

## 🔧 Development Prerequisites

### 1. Environment Files Setup

Create and configure your development environment files:

#### `.env.dev` (Development Environment Variables)
```bash
# Database Configuration
POSTGRES_DB=your_dev_db
POSTGRES_USER=yudai_user
POSTGRES_PASSWORD=yudai_password

# API Configuration
VITE_API_BASE_URL=http://localhost:8001

# Application Settings
NODE_ENV=development
DEBUG=true

# GitHub OAuth (Development)
FRONTEND_BASE_URL=http://localhost:3000
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
API_DOMAIN=localhost:8001
DEV_DOMAIN=localhost:3000

# Security (Development keys - CHANGE IN PRODUCTION)
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET=dev-jwt-secret-change-in-production

# Docker Compose
DOCKER_COMPOSE=true
```

#### `.env.dev.secrets` (API Keys & Secrets)
```bash
# ===========================================
# DEVELOPMENT SECRETS
# Add your actual API keys here
# ===========================================

# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-your-actual-openrouter-key

# GitHub App Configuration
GITHUB_APP_ID=your_github_app_id
GITHUB_APP_CLIENT_ID=your_github_app_client_id
GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret
GITHUB_APP_INSTALLATION_ID=your_github_app_installation_id
```

### 2. GitHub Private Key
Ensure you have the GitHub private key file:
```bash
# File location
./backend/yudaiv3.2025-08-02.private-key.pem

# Verify file exists
ls -la ./backend/yudaiv3.2025-08-02.private-key.pem
```

## 📍 Development Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:3000 | React application with hot reload |
| **Backend API** | http://localhost:8001 | FastAPI backend with debug logging |
| **Database** | localhost:5433 | PostgreSQL (${POSTGRES_DB}, yudai_user, yudai_password) |
| **Health Check** | http://localhost:3000/health | Frontend health endpoint |

## 🐳 Development Docker Configuration

### Services Overview

| Service | Container | Dockerfile | Ports | Purpose |
|---------|-----------|------------|-------|---------|
| **Database** | `yudai-db-dev` | `backend/db/Dockerfile` | 5433:5432 | PostgreSQL with dev tuning |
| **Backend** | `yudai-be-dev` | `backend/Dockerfile.dev` | 8001:8000 | FastAPI with debug tools |
| **Frontend** | `yudai-fe-dev` | `Dockerfile.dev` | 3000:80 | React with nginx (dev config) |

### Key Development Features

- ✅ **Hot Reload**: Frontend changes reflect immediately
- ✅ **Debug Logging**: Full SQL echo and application logs
- ✅ **Database Access**: Direct connection for development
- ✅ **Debug Tools**: vim, htop, sudo access in backend container
- ✅ **No SSL**: HTTP only for faster development
- ✅ **Volume Mounts**: Live code changes without rebuild

---

# 🏭 PRODUCTION ENVIRONMENT SETUP

## Quick Production Start

```bash
# 1. Setup production environment files
cp .env.prod.example .env.prod
cp .env.secrets.example .env.secrets
# Edit files with your production values

# 2. Setup SSL certificates
mkdir -p ssl/
# Place your certificates: ssl/fullchain.pem, ssl/privkey.pem

# 3. Start production environment
docker compose -f docker-compose.prod.yml up -d

# 4. Check health
docker compose -f docker-compose.prod.yml ps

# 5. View logs
docker compose -f docker-compose.prod.yml logs -f
```

## 🔧 Production Prerequisites

### 1. Production Environment Files

#### `.env.prod` (Production Environment Variables)
```bash
# ===========================================
# PRODUCTION ENVIRONMENT VARIABLES
# ===========================================

# Database Configuration
POSTGRES_DB=your_prod_db
POSTGRES_USER=your_prod_user
POSTGRES_PASSWORD=your_secure_prod_password

# API Configuration
VITE_API_BASE_URL=https://api.yudai.app

# Application Settings
NODE_ENV=production
DEBUG=false

# GitHub OAuth (Production)
FRONTEND_BASE_URL=https://yudai.app
GITHUB_REDIRECT_URI=https://yudai.app/auth/callback
API_DOMAIN=api.yudai.app
DEV_DOMAIN=yudai.app

# Security (Use strong keys in production)
SECRET_KEY=your-production-secret-key
JWT_SECRET=your-production-jwt-secret

# Docker Compose
DOCKER_COMPOSE=true
```

#### `.env.secrets` (Production API Keys & Secrets)
```bash
# ===========================================
# PRODUCTION SECRETS
# NEVER COMMIT THIS FILE
# ===========================================

# OpenRouter API (Production Key)
OPENROUTER_API_KEY=sk-or-v1-your-production-openrouter-key

# GitHub App Configuration (Production)
GITHUB_APP_ID=your_prod_github_app_id
GITHUB_APP_CLIENT_ID=your_prod_github_app_client_id
GITHUB_APP_CLIENT_SECRET=your_prod_github_app_client_secret
GITHUB_APP_INSTALLATION_ID=your_prod_github_app_installation_id
```

### 2. SSL Certificates Setup

```bash
# Create SSL directory
mkdir -p ssl/

# Place your certificates (Let's Encrypt example)
# ssl/fullchain.pem - Full certificate chain
# ssl/privkey.pem   - Private key

# Set proper permissions
chmod 600 ssl/privkey.pem
chmod 644 ssl/fullchain.pem
```

### 3. DNS Configuration

Configure your domain DNS records:

```
# A Records
yudai.app      -> YOUR_SERVER_IP
api.yudai.app  -> YOUR_SERVER_IP
dev.yudai.app  -> YOUR_SERVER_IP
```

## 📍 Production Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | https://yudai.app | Production React application |
| **Backend API** | https://api.yudai.app | Production FastAPI backend |
| **Health Check** | https://yudai.app/health | Frontend health endpoint |

## 🐳 Production Docker Configuration

### Services Overview

| Service | Container | Dockerfile | Ports | Purpose |
|---------|-----------|------------|-------|---------|
| **Database** | `yudai-db` | `backend/db/Dockerfile` | Internal only | PostgreSQL with prod tuning |
| **Backend** | `yudai-be` | `backend/Dockerfile` | 8000:8000 | FastAPI optimized |
| **Frontend** | `yudai-fe` | `Dockerfile` | 80:80, 443:443 | React with nginx (SSL) |

### Key Production Features

- ✅ **SSL/TLS**: HTTPS with certificate validation
- ✅ **Resource Limits**: CPU and memory constraints
- ✅ **Security Hardening**: No sudo, minimal privileges, apparmor
- ✅ **Production Logging**: Structured JSON logs with rotation
- ✅ **Health Checks**: Comprehensive monitoring
- ✅ **Backup Volumes**: Automated data persistence

---

# 📊 ENVIRONMENT COMPARISON TABLES

## 🐳 Docker Compose Files Comparison

### Services Configuration

| Service | Dev Container | Prod Container | Dev Dockerfile | Prod Dockerfile |
|---------|---------------|----------------|----------------|----------------|
| **Database** | `yudai-db-dev` | `yudai-db` | `backend/db/Dockerfile` | `backend/db/Dockerfile` |
| **Backend** | `yudai-be-dev` | `yudai-be` | `backend/Dockerfile.dev` | `backend/Dockerfile` |
| **Frontend** | `yudai-fe-dev` | `yudai-fe` | `Dockerfile.dev` | `Dockerfile` |

### Port Mapping

| Service | Development | Production | Purpose |
|---------|-------------|------------|---------|
| **Frontend** | 3000:80 | 80:80, 443:443 | HTTP/HTTPS access |
| **Backend** | 8001:8000 | 8000:8000 | API access |
| **Database** | 5433:5432 | Internal only | Database access |

### Environment Variables

| Variable | Development | Production | Purpose |
|----------|-------------|------------|---------|
| `POSTGRES_DB` | your_dev_db | ${POSTGRES_DB} | Database name |
| `DEBUG` | true | false | Debug logging |
| `DB_ECHO` | true | false | SQL query logging |
| `VITE_API_BASE_URL` | http://localhost:8001 | https://api.yudai.app | Frontend API URL |
| `NODE_ENV` | development | production | Environment mode |

### Volume Mounts

| Volume | Development | Production | Purpose |
|--------|-------------|------------|---------|
| **Backend Code** | `./backend:/app` | `./backend:/app` | Live code mounting |
| **Frontend Code** | `./src:/app/src` | N/A (built) | Development hot reload |
| **SSL Certs** | N/A | `./ssl:/etc/nginx/ssl:ro` | SSL certificates |
| **Logs** | `./logs/dev:/app/logs` | `./logs:/app/logs` | Application logs |

### Resource Limits

| Resource | Development | Production | Purpose |
|----------|-------------|------------|---------|
| **CPU Limits** | Unlimited | 2.0 cores | CPU resource control |
| **Memory Limits** | Unlimited | 2GB (BE), 512MB (FE) | Memory resource control |
| **Restart Policy** | unless-stopped | on-failure | Container restart behavior |

## 🔒 Security Configuration

| Security Feature | Development | Production | Impact |
|------------------|-------------|------------|--------|
| **SSL/TLS** | ❌ Disabled | ✅ Enabled | HTTPS encryption |
| **User Privileges** | sudo access | no sudo | Container security |
| **Network Isolation** | bridge network | bridge network | Service isolation |
| **Resource Limits** | ❌ None | ✅ Strict | Resource protection |
| **Debug Tools** | vim, htop | ❌ None | Attack surface |
| **AppArmor** | ❌ Disabled | ✅ Enabled | System security |

## 📋 Nginx Configuration Comparison

| Feature | Development | Production | Configuration File |
|---------|-------------|------------|-------------------|
| **SSL** | ❌ HTTP only | ✅ HTTPS + HTTP redirect | nginx.dev.conf vs nginx.prod.conf |
| **Domains** | localhost | yudai.app, api.yudai.app | server_name directive |
| **Certificates** | N/A | fullchain.pem, privkey.pem | ssl_certificate directives |
| **API Proxy** | /api/ → backend:8000 | /api/ → backend:8000 | location blocks |
| **Auth Routes** | /auth/api/ → backend:8000 | /auth/api/ → backend:8000 | location blocks |
| **Security Headers** | Basic | Full (CSP, HSTS, etc.) | add_header directives |

---

# 🚨 TROUBLESHOOTING GUIDE

## Development Environment Issues

### Check Service Status
```bash
# Check all services
docker compose -f docker-compose-dev.yml ps

# Check specific service health
docker compose -f docker-compose-dev.yml exec backend curl -f http://localhost:8000/health
```

### View Logs
```bash
# All services
docker compose -f docker-compose-dev.yml logs -f

# Specific service
docker compose -f docker-compose-dev.yml logs backend -f

# Last 100 lines
docker compose -f docker-compose-dev.yml logs --tail=100
```

### Common Development Issues

#### Port Conflicts
```bash
# Check what's using ports
lsof -i :3000
lsof -i :8001
lsof -i :5433

# Stop conflicting services or change ports in docker-compose-dev.yml
```

#### Database Connection Issues
```bash
# Connect directly to database
docker compose -f docker-compose-dev.yml exec db psql -U yudai_user -d $POSTGRES_DB

# Reset database
docker compose -f docker-compose-dev.yml down -v
docker compose -f docker-compose-dev.yml up --build
```

#### Permission Issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
chmod 600 .env.dev.secrets
```

### Rebuild and Restart
```bash
# Clean rebuild
docker compose -f docker-compose-dev.yml down
docker compose -f docker-compose-dev.yml build --no-cache
docker compose -f docker-compose-dev.yml up -d

# Force fresh start with new database
docker compose -f docker-compose-dev.yml down -v
docker compose -f docker-compose-dev.yml up --build
```

## Production Environment Issues

### SSL Certificate Issues
```bash
# Check certificate validity
openssl x509 -in ssl/fullchain.pem -text -noout

# Test SSL connection
curl -v https://yudai.app/health

# Check nginx SSL configuration
docker compose -f docker-compose.prod.yml exec frontend nginx -t
```

### Resource Issues
```bash
# Check resource usage
docker compose -f docker-compose.prod.yml stats

# View container logs for OOM errors
docker compose -f docker-compose.prod.yml logs | grep -i "killed\|oom"
```

### Database Issues
```bash
# Check database health
docker compose -f docker-compose.prod.yml exec db pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# Backup database
docker compose -f docker-compose.prod.yml exec db pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > backup.sql
```

### Production Rebuild
```bash
# Rolling update (zero downtime)
docker compose -f docker-compose.prod.yml up -d --build

# Complete restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build
```

---

# 📚 QUICK REFERENCE

## Development Commands
```bash
# Start
docker compose -f docker-compose-dev.yml up -d

# Stop
docker compose -f docker-compose-dev.yml down

# Logs
docker compose -f docker-compose-dev.yml logs -f

# Rebuild
docker compose -f docker-compose-dev.yml up --build

# Clean restart
docker compose -f docker-compose-dev.yml down -v && docker compose -f docker-compose-dev.yml up --build
```

## Production Commands
```bash
# Start
docker compose -f docker-compose.prod.yml up -d

# Stop
docker compose -f docker-compose.prod.yml down

# Logs
docker compose -f docker-compose.prod.yml logs -f

# Rolling update
docker compose -f docker-compose.prod.yml up -d --build

# Emergency stop
docker compose -f docker-compose.prod.yml down --remove-orphans
```

## Health Check URLs
```bash
# Development
curl http://localhost:3000/health     # Frontend
curl http://localhost:8001/health     # Backend

# Production
curl https://yudai.app/health         # Frontend
curl https://api.yudai.app/health     # Backend
```

## Environment File Templates

### Development Template
```bash
cp .env.dev.example .env.dev
cp .env.dev.secrets.example .env.dev.secrets
# Edit with your development values
```

### Production Template
```bash
cp .env.prod.example .env.prod
cp .env.secrets.example .env.secrets
# Edit with your production values
```

---

# 🎯 SUMMARY

## Environment Separation Achieved ✅

- **Complete Isolation**: Production and development run independently
- **Configuration Only**: No code changes between environments
- **Security**: Production hardening vs development accessibility
- **Scalability**: Different resource allocations and limits
- **Monitoring**: Environment-specific logging and health checks

## Key Benefits

1. **🚀 Fast Development**: Hot reload, debug tools, direct database access
2. **🔒 Production Security**: SSL, resource limits, minimal privileges
3. **📊 Easy Deployment**: Separate docker-compose files for each environment
4. **🔄 Zero Downtime Updates**: Rolling updates in production
5. **📝 Clear Documentation**: Comprehensive setup and troubleshooting guides

Both environments are now fully configured with proper separation of concerns while maintaining the same powerful YudaiV3 application functionality.
