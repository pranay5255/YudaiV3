# YudaiV3 Production Deployment Guide

## Overview

This guide covers the complete production deployment setup for YudaiV3, including all configuration differences between development and production environments.

## Configuration Files Analysis

### 1. Docker Compose Differences

#### `docker-compose-dev.yml` vs `docker-compose.prod.yml`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **Database** | `yudai_dev` | Environment variables (`${POSTGRES_DB}`) |
| **Ports** | DB: 5433, Backend: 8001, Frontend: 3000 | DB: Internal, Backend: 8000, Frontend: 80/443 |
| **Resource Limits** | None | None (unlimited for flexibility) |
| **Security** | Basic | Security hardening, capabilities, privileges |
| **Logging** | Basic | Structured JSON logging with rotation |
| **Health Checks** | Basic | Enhanced with better timing |
| **Volumes** | Development paths | Production backup paths |
| **Environment** | Debug enabled | Production optimized |

**Production-Specific Features:**
- Security hardening (no-new-privileges, apparmor, capability drops)
- Production PostgreSQL tuning (200 connections, 256MB shared buffers, etc.)
- Enhanced health checks with proper timeouts
- Network isolation with custom subnet (172.20.0.0/16)
- Backup volume management
- Unlimited resources for maximum flexibility

### 2. Backend Dockerfile Differences

#### `backend/Dockerfile.dev` vs `backend/Dockerfile`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **User** | Root user | Non-root user (`appuser`) |
| **Dependencies** | `libpq-dev` (dev) | `postgresql-client` (minimal) |
| **Caching** | No cache purge | `--no-cache-dir` and `pip cache purge` |
| **Health Check** | 15s interval | 30s interval |
| **Security** | Basic | User permissions, minimal privileges |

**Production Security Features:**
- Non-root user execution
- Minimal system dependencies
- Cache cleanup for smaller image size
- Proper file permissions

### 3. Frontend Dockerfile Differences

#### `Dockerfile.dev` vs `Dockerfile`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **Build Process** | Single stage (Vite dev server) | Multi-stage (builder + nginx) |
| **Server** | Vite dev server with hot reload | Nginx alpine for static file serving |
| **Ports** | 3000 (dev) | 80/443 (HTTP/HTTPS) |
| **Static Assets** | Hot reload, source maps | Pre-built optimized assets, minified |
| **Environment** | `NODE_ENV=development` | Production build with `VITE_API_BASE_URL` |
| **Health Check** | Checks `localhost:3000` | Checks `localhost/health` |
| **Image Size** | Larger (includes dev dependencies) | Smaller (only production assets) |
| **Security** | Root user, full Node.js access | Nginx user, read-only static files |

**Production Deployment Impact:**
- **Build Time**: Multi-stage build reduces final image size by ~70-80%
- **Security**: No Node.js runtime in production image, reducing attack surface
- **Performance**: Pre-built optimized assets load faster
- **Resource Usage**: Smaller image footprint, faster container startup
- **SSL Support**: Built-in HTTPS support with certificate mounting
- **Health Monitoring**: Dedicated health endpoint for load balancers

**Build Arguments Required:**
```dockerfile
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
```

**Volume Mounts for SSL:**
```yaml
volumes:
  - /etc/nginx/ssl/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
  - /etc/nginx/ssl/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
```

### 4. Nginx Configuration Differences

#### `nginx.dev.conf` vs `nginx.prod.conf`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **SSL/TLS** | HTTP only (port 80) | HTTPS with SSL certificates (port 443) |
| **Security Headers** | Minimal (`server_tokens off`) | Comprehensive security headers |
| **CORS Origin** | `http://localhost:3000` | `https://yudai.app` |
| **Server Names** | `localhost` only | Multiple domains + redirect |
| **SSL Protocols** | N/A | TLSv1.2/TLSv1.3 only |
| **HTTP Redirect** | None | Automatic HTTP to HTTPS redirect |
| **Certificate Paths** | N/A | `/etc/nginx/ssl/fullchain.pem` |
| **API Routes Include** | Absolute host path | Container-relative path |

**Production Security Features:**
- **SSL/TLS Encryption**: Full HTTPS with Let's Encrypt certificates
- **Security Headers**:
  - `Strict-Transport-Security`: Forces HTTPS for 1 year
  - `X-Frame-Options`: Prevents clickjacking attacks
  - `X-Content-Type-Options`: Prevents MIME type sniffing
  - `X-XSS-Protection`: Enables XSS filtering
- **Domain-based Routing**: Supports multiple subdomains
- **Certificate-based Authentication**: SSL client certificates ready

**Deployment Impact:**
- **SSL Certificate Management**: Requires Let's Encrypt setup and renewal
- **Domain Configuration**: DNS pointing to server IP required
- **Firewall Rules**: Must allow ports 80/443, block port 3000
- **Certificate Mounting**: Docker volumes for certificate files
- **HTTP Redirect**: All traffic automatically redirected to HTTPS
- **API Route Configuration**: Requires `api-routes.conf` template file

**SSL Certificate Requirements:**
```bash
# Certificate files needed:
/etc/letsencrypt/live/yudai.app/fullchain.pem
/etc/letsencrypt/live/yudai.app/privkey.pem
```

**Domain Configuration Required:**
```bash
# DNS A records:
yudai.app      → YOUR_SERVER_IP
www.yudai.app  → YOUR_SERVER_IP
api.yudai.app  → YOUR_SERVER_IP
dev.yudai.app  → YOUR_SERVER_IP
```

## Production Setup Steps

### Prerequisites

1. **Domain Setup**
   ```bash
   # Point these domains to your server IP:
   # - yudai.app
   # - www.yudai.app
   # - api.yudai.app (optional)
   # - dev.yudai.app (optional)
   ```

2. **SSL Certificates**
   ```bash
   # Install certbot for Let's Encrypt
   sudo apt update
   sudo apt install certbot

   # Generate SSL certificates
   sudo certbot certonly --standalone -d yudai.app -d www.yudai.app

   # Certificates will be saved to:
   # /etc/letsencrypt/live/yudai.app/fullchain.pem
   # /etc/letsencrypt/live/yudai.app/privkey.pem
   ```

3. **Environment Variables Setup**

   Create production environment files:

   **`.env.prod`** (Application Configuration)
   ```bash
   # Domain Configuration
   DOMAIN=yudai.app
   FRONTEND_URL=https://yudai.app
   BACKEND_URL=https://yudai.app/api
   API_DOMAIN=yudai.app
   DEV_DOMAIN=yudai.app

   # Database Configuration
   POSTGRES_DB=yudai_prod
   POSTGRES_USER=yudai_user
   POSTGRES_PASSWORD=your_secure_db_password

   # Authentication
   SECRET_KEY=your_256_bit_secret_key
   JWT_SECRET=your_jwt_secret_key

   # GitHub App OAuth (Production)
   GITHUB_APP_ID=your_github_app_id
   GITHUB_APP_CLIENT_ID=your_github_app_client_id
   GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret
   GITHUB_APP_PRIVATE_KEY_PATH=/app/yudaiv3.2025-08-02.private-key.pem
   GITHUB_APP_INSTALLATION_ID=your_installation_id

   # API Configuration
   HOST=0.0.0.0
   PORT=8000
   SALT=your_salt_value

   # OpenRouter API
   OPENROUTER_API_KEY=your_openrouter_api_key

   # SWE-agent Configuration
   SWEAGENT_CONFIG_PATH=/app/solver/config.yaml
   SWEAGENT_DATA_PATH=/data/swe_runs
   MAX_SOLVE_TIME_MINUTES=30
   MAX_CONCURRENT_SOLVES=3
   SOLVER_TIMEOUT_SECONDS=1800
   ```

   **`.env.secrets`** (Secrets - Keep separate and secure)
   ```bash
   # GitHub App Credentials (same as above for consistency)
   GITHUB_APP_CLIENT_ID=your_github_app_client_id
   GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret

   # Additional secrets if needed
   ```

4. **GitHub App Setup (Production)**

   Create a new GitHub App for production:
   ```bash
   # 1. Go to https://github.com/settings/apps
   # 2. Create new GitHub App with:
   #    - Name: YudaiV3 Production
   #    - Homepage URL: https://yudai.app
   #    - Callback URL: https://yudai.app/auth/callback
   # 3. Generate and download private key
   # 4. Install the app on your repositories
   # 5. Note the App ID and Installation ID
   ```

5. **SSL Certificate Symlinks**

   Create symlinks for nginx SSL configuration:
   ```bash
   sudo mkdir -p /etc/nginx/ssl
   sudo ln -s /etc/letsencrypt/live/yudai.app/fullchain.pem /etc/nginx/ssl/fullchain.pem
   sudo ln -s /etc/letsencrypt/live/yudai.app/privkey.pem /etc/nginx/ssl/privkey.pem
   ```

6. **Directory Structure Setup**

   ```bash
   # Create required directories
   sudo mkdir -p /opt/yudai
   sudo mkdir -p /opt/yudai/backups/postgres
   sudo mkdir -p /opt/yudai/logs
   sudo mkdir -p /opt/yudai/data/swe_runs

   # Set proper permissions
   sudo chown -R $USER:$USER /opt/yudai
   ```

7. **GitHub App Private Key**

   Place your production GitHub App private key:
   ```bash
   # Copy to backend directory
   cp yudaiv3.2025-08-02.private-key.pem backend/

   # Set proper permissions
   chmod 600 backend/yudaiv3.2025-08-02.private-key.pem
   ```

### Deployment Commands

1. **Initial Production Deployment**
   ```bash
   # Build and start production services
   docker compose -f docker-compose.prod.yml up -d --build

   # Check service status
   docker compose -f docker-compose.prod.yml ps

   # View logs
   docker compose -f docker-compose.prod.yml logs -f
   ```

2. **SSL Certificate Renewal**
   ```bash
   # Test renewal
   sudo certbot renew --dry-run

   # Add to crontab for automatic renewal
   sudo crontab -e
   # Add: 0 12 * * * /usr/bin/certbot renew --quiet

   # After renewal, restart nginx
   docker compose -f docker-compose.prod.yml restart frontend
   ```

3. **Database Backup**
   ```bash
   # Manual backup
   docker exec yudai-db pg_dump -U yudai_user yudai_prod > backup_$(date +%Y%m%d_%H%M%S).sql

   # Automated backup script (create /opt/yudai/backup.sh)
   #!/bin/bash
   BACKUP_DIR="/opt/yudai/backups"
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   docker exec yudai-db pg_dump -U yudai_user yudai_prod > "$BACKUP_DIR/backup_$TIMESTAMP.sql"
   find "$BACKUP_DIR" -name "backup_*.sql" -mtime +7 -delete
   ```

### Monitoring and Maintenance

1. **Health Checks**
   ```bash
   # Check all services
   curl -f https://yudai.app/health
   curl -f https://yudai.app/api/health

   # Docker health status
   docker compose -f docker-compose.prod.yml ps
   ```

2. **Log Monitoring**
   ```bash
   # View application logs
   docker compose -f docker-compose.prod.yml logs -f backend
   docker compose -f docker-compose.prod.yml logs -f frontend

   # System monitoring
   docker stats
   ```

3. **Performance Monitoring**
   ```bash
   # Resource usage
   docker compose -f docker-compose.prod.yml top

   # Database monitoring
   docker exec -it yudai-db psql -U yudai_user -d yudai_prod -c "SELECT * FROM pg_stat_activity;"
   ```

### Security Considerations

1. **Firewall Configuration**
   ```bash
   # UFW configuration
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw allow ssh
   sudo ufw --force enable
   ```

2. **SSL/TLS Security**
   - Certificates auto-renew via Let's Encrypt
   - TLS 1.2/1.3 only
   - Strong cipher suites
   - HSTS enabled

3. **Container Security**
   - Non-root users
   - Minimal base images
   - No privileged containers
   - Resource limits enforced

### Troubleshooting

1. **SSL Certificate Issues**
   ```bash
   # Check certificate validity
   openssl x509 -in /etc/nginx/ssl/fullchain.pem -text -noout

   # Renew certificates manually
   sudo certbot renew
   ```

2. **Service Startup Issues**
   ```bash
   # Check service logs
   docker compose -f docker-compose.prod.yml logs [service_name]

   # Restart specific service
   docker compose -f docker-compose.prod.yml restart [service_name]
   ```

3. **Database Connection Issues**
   ```bash
   # Test database connectivity
   docker exec -it yudai-db psql -U yudai_user -d yudai_prod -c "SELECT version();"

   # Check database logs
   docker compose -f docker-compose.prod.yml logs db
   ```

### Scaling Considerations

1. **Horizontal Scaling**
   - Add load balancer for multiple backend instances
   - Use Redis for session storage
   - Implement database read replicas

2. **Server Scaling**
   - Monitor resource usage with `docker stats`
   - Scale server resources based on application needs
   - Consider upgrading server specifications as usage grows

### Backup and Recovery

1. **Automated Backups**
   ```bash
   # Database backups (daily)
   # Application logs rotation
   # SSL certificate backups
   ```

2. **Disaster Recovery**
   ```bash
   # Restore from backup
   docker exec -i yudai-db psql -U yudai_user -d yudai_prod < backup_file.sql

   # Full system restore procedure
   ```

## Summary of Key Production Differences

1. **Security First**: SSL, non-root users, minimal privileges
2. **Performance Optimized**: Unlimited resources, caching, optimized builds
3. **Monitoring Ready**: Health checks, structured logging, metrics
4. **Production Hardened**: SSL certificates, firewall, backups
5. **Scalable Architecture**: Load balancing ready, resource management
6. **Automated Maintenance**: Certificate renewal, log rotation, backups

This deployment setup provides a production-ready, secure, and maintainable environment for YudaiV3.

## API Configuration Verification & Fixes

### 🔍 Analysis Results

**✅ What's Working:**
- Route definitions in `backend/config/routes.py` are consistent
- Frontend API configuration in `src/config/api.ts` matches backend routes
- Docker Compose production environment variables are properly structured
- Nginx template includes proper CORS and proxy headers

**❌ Critical Issues Found:**

#### 1. API Base URL Configuration Mismatch
**Problem:** Frontend is configured to use external domain for API calls, but nginx handles internal routing.

**Current Configuration:**
```yaml
# docker-compose.prod.yml
- VITE_API_BASE_URL=${VITE_API_BASE_URL:-https://yudai.app}
```

**Issue:** Frontend makes calls to `https://yudai.app/auth/api/login` but nginx should handle these internally.

#### 2. Nginx Route Prefix Inconsistency
**Problem:** Nginx template expects `/api/*` prefix but backend routes use `/auth/*`, `/daifu/*`, etc.

**Nginx Template (`api-routes.conf`):**
```nginx
location /api/ {
    rewrite ^/api/(.*)$ /$1 break;  # Removes /api prefix
    proxy_pass http://backend:8000;
}
```

**Backend Routes (`routes.py`):**
```python
AUTH_LOGIN = f"{AUTH_PREFIX}/api/login"  # /auth/api/login
DAIFU_SESSIONS = DAIFU_PREFIX            # /daifu
```

**Issue:** Frontend calls `/auth/api/login` but nginx expects `/api/auth/api/login`.

### 🔧 Required Fixes

#### Fix 1: Update Docker Compose API Base URL
```yaml
# In docker-compose.prod.yml, change:
environment:
  - VITE_API_BASE_URL=${VITE_API_BASE_URL:-}  # Empty for nginx routing
  # OR use relative URLs
  - VITE_API_BASE_URL=${VITE_API_BASE_URL:-""}
```

#### Fix 2: Update Nginx API Routes Configuration
**Current:** Routes with `/api` prefix → backend
**Required:** Direct routing without `/api` prefix

Update `nginx/templates/api-routes.conf`:
```nginx
# Remove /api prefix requirement and route directly
location /auth/ {
    proxy_pass http://backend:8000;
    # ... existing proxy headers
}

location /daifu/ {
    proxy_pass http://backend:8000;
    # ... existing proxy headers
}

location /github/ {
    proxy_pass http://backend:8000;
    # ... existing proxy headers
}

# Keep /api/ for future standardized routes if needed
location /api/ {
    proxy_pass http://backend:8000/api/;
    # ... existing proxy headers
}
```

#### Fix 3: Update Frontend API Configuration
Update `src/config/api.ts` to use relative URLs:
```typescript
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || '',  // Empty string for nginx routing
  // ... rest of configuration remains the same
};
```

#### Fix 4: CORS Origin Configuration
Ensure nginx template has proper CORS origin:
```nginx
# In nginx.prod.conf
set $cors_origin "https://yudai.app";

# In nginx.dev.conf
set $cors_origin "http://localhost:3000";
```

### 📋 Implementation Plan

#### Phase 1: Environment Configuration (Immediate)
1. **Update `docker-compose.prod.yml`:**
   ```yaml
   environment:
     - VITE_API_BASE_URL=""  # Empty for nginx internal routing
   ```

2. **Update `.env.prod` template:**
   ```bash
   VITE_API_BASE_URL=""
   ```

#### Phase 2: Nginx Configuration (Next)
1. **Update `nginx/templates/api-routes.conf`:**
   - Add direct routing for `/auth/*`, `/daifu/*`, `/github/*`
   - Keep `/api/*` for future standardized routes
   - Ensure CORS headers are properly configured

2. **Update main nginx configs:**
   - Ensure `$cors_origin` is set correctly
   - Verify SSL certificate paths

#### Phase 3: Frontend Configuration (If Needed)
1. **Verify `src/config/api.ts`:**
   - Confirm relative URL handling works correctly
   - Test API calls in production environment

#### Phase 4: Testing & Validation
1. **Test API endpoints:**
   ```bash
   # Test auth endpoints
   curl -k https://yudai.app/auth/api/login

   # Test daifu endpoints
   curl -k https://yudai.app/daifu/sessions

   # Test health endpoints
   curl -k https://yudai.app/health
   curl -k https://yudai.app/api/health
   ```

2. **Validate CORS configuration:**
   - Check browser network tab for CORS headers
   - Verify preflight OPTIONS requests work

### 🚨 Deployment Impact

**Before Fix:**
- Frontend makes external API calls to `https://yudai.app/auth/api/login`
- Nginx tries to route `/auth/api/login` but expects `/api/auth/api/login`
- Results in 404 errors or routing failures

**After Fix:**
- Frontend makes relative API calls (empty base URL)
- Nginx routes `/auth/*`, `/daifu/*` directly to backend
- Proper internal service communication

### 📝 Next Steps

1. **Immediate Action Required:**
   - Update `docker-compose.prod.yml` to use empty `VITE_API_BASE_URL`
   - Update nginx template for direct route handling

2. **Configuration Files to Update:**
   - `docker-compose.prod.yml`
   - `nginx/templates/api-routes.conf`
   - `nginx.prod.conf` (CORS origin)
   - `nginx.dev.conf` (CORS origin)

3. **Testing Requirements:**
   - Full API endpoint testing in production
   - CORS validation
   - SSL certificate verification

4. **Monitoring:**
   - Check nginx access logs for 404 errors on API routes
   - Monitor backend logs for routing issues
   - Validate frontend-backend communication

### ⚠️ Critical Path

**This is a blocking issue for production deployment.** The current configuration will cause API calls to fail because:
- Frontend expects nginx to proxy API calls
- Nginx expects `/api/` prefixed routes
- Backend provides routes without `/api/` prefix

Fix these routing inconsistencies before production deployment.
