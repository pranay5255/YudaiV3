# YudaiV3 Production Setup

This document outlines the production configuration for YudaiV3, including all the changes made to ensure consistency between development and production environments.

## Overview

The production setup consists of three main services:
1. **Database Service** (`db`) - PostgreSQL database
2. **Backend Service** (`backend`) - FastAPI application
3. **Frontend Service** (`frontend`) - React application with Nginx

## Configuration Files

### 1. Docker Compose Files

#### Development (`docker-compose.yml`)
- **Services**: `db`, `backend`
- **Ports**: Backend exposed on `8000`
- **Environment**: Development-friendly with debug settings
- **Networking**: Internal Docker network

#### Production (`docker-compose.prod.yml`)
- **Services**: `db`, `backend`, `frontend`
- **Ports**: 
  - Backend: `127.0.0.1:8000` (localhost only)
  - Frontend: `80` (HTTP), `443` (HTTPS)
- **Environment**: Production-optimized settings
- **SSL**: Configured with certificate mounting

### 2. Nginx Configuration Files

#### Development (`nginx.conf`)
- **Protocol**: HTTP only
- **Domains**: `localhost`
- **CORS**: Allow all origins (`*`)
- **Proxy Rules**:
  - `/auth/*` → `backend:8000/auth/*`
  - `/api/*` → `backend:8000/*` (prefix removal)

#### Production (`nginx.prod.conf`)
- **Protocol**: HTTPS with SSL termination
- **Domains**: 
  - `yudai.app` (main application)
  - `api.yudai.app` (API subdomain)
  - `dev.yudai.app` (development subdomain)
- **CORS**: Restricted to specific domains
- **Security**: Full SSL/TLS configuration with security headers

## API Endpoint Consistency

### Backend API Structure
All backend endpoints are consistently available in both environments:

```
/                    - API information
/health             - Health check
/auth/*             - Authentication endpoints
/github/*           - GitHub integration
/daifu/*            - Chat services
/issues/*           - Issue management
/filedeps/*         - File dependencies
```

### Frontend API Integration
The frontend uses consistent API patterns:

```typescript
// API endpoints (with /api prefix)
const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app/api');

// Auth endpoints (direct proxy)
const AUTH_BASE_URL = getAuthBaseURL();
```

## Environment Variables

### Development Environment
```bash
DATABASE_URL=postgresql://yudai_user:yudai_password@db:5432/yudai_db
DB_ECHO=true
GITHUB_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_API_URL=http://localhost:8000
```

### Production Environment
```bash
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
DB_ECHO=false
GITHUB_REDIRECT_URI=https://yudai.app/auth/callback
VITE_API_URL=https://yudai.app/api
API_DOMAIN=api.yudai.app
DEV_DOMAIN=dev.yudai.app
```

## Key Changes Made

### 1. Production Docker Compose Updates
- ✅ Fixed frontend service configuration
- ✅ Updated health check URLs
- ✅ Added proper environment variable handling
- ✅ Configured SSL certificate mounting

### 2. Production Nginx Configuration Updates
- ✅ Added separate `/auth/*` proxy rules
- ✅ Fixed API proxy with prefix removal (`/api/*` → `backend:8000/*`)
- ✅ Added proper CORS headers for each domain
- ✅ Added backend down error handling
- ✅ Added security headers and SSL configuration
- ✅ Added proper timeout and buffer settings

### 3. API Consistency Verification
- ✅ All backend endpoints working correctly
- ✅ Authentication flow consistent
- ✅ File dependencies API functional
- ✅ GitHub integration endpoints available
- ✅ Chat services operational
- ✅ Issue management endpoints working

## Testing Results

### Development Environment
```bash
✅ Backend health: http://localhost:8000/health
✅ API root: http://localhost:8000/
✅ File dependencies: http://localhost:8000/filedeps/
✅ Auth endpoints: http://localhost:8000/auth/config
✅ Database connectivity: Healthy
✅ Container status: All healthy
```

### Production Environment
```bash
✅ Build successful: All services built without errors
✅ Frontend build: React app compiled successfully
✅ Nginx configuration: Valid and functional
✅ SSL configuration: Properly configured
✅ Proxy rules: All endpoints properly routed
```

## Deployment Commands

### Development
```bash
# Start development environment
docker compose up -d

# View logs
docker compose logs -f

# Stop development environment
docker compose down
```

### Production
```bash
# Start production environment
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop production environment
docker compose -f docker-compose.prod.yml down

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

## SSL Certificate Setup

For production deployment, SSL certificates should be placed in:
```
./ssl/
├── fullchain.pem    # Full certificate chain
└── privkey.pem      # Private key
```

## Security Considerations

### Production Security Features
- ✅ HTTPS enforcement with HSTS
- ✅ SSL/TLS 1.2+ protocols
- ✅ Modern cipher suites
- ✅ Security headers (X-Frame-Options, CSP, etc.)
- ✅ CORS restrictions to specific domains
- ✅ Backend service isolation (localhost only)
- ✅ File access restrictions (block .git, .env files)

### Authentication Security
- ✅ GitHub OAuth integration
- ✅ JWT token management
- ✅ Secure token storage
- ✅ Automatic token refresh
- ✅ Proper logout handling

## Monitoring and Health Checks

### Container Health Checks
- **Database**: PostgreSQL readiness check
- **Backend**: HTTP health endpoint
- **Frontend**: Nginx health endpoint

### Health Endpoints
- `GET /health` - Backend health check
- `GET /` - Frontend health check (nginx)

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**
   - Verify certificate files in `./ssl/`
   - Check certificate expiration
   - Validate domain names

2. **CORS Errors**
   - Verify nginx CORS headers
   - Check frontend API_BASE_URL
   - Validate allowed origins

3. **Authentication Failures**
   - Verify GitHub OAuth app configuration
   - Check GITHUB_REDIRECT_URI matches
   - Validate environment variables

4. **Database Connection Issues**
   - Check DATABASE_URL format
   - Verify PostgreSQL container health
   - Validate network connectivity

### Debug Commands
```bash
# Check container status
docker ps

# View container logs
docker logs yudai-be
docker logs yudai-fe

# Test nginx configuration
docker exec yudai-fe nginx -t

# Test backend connectivity
curl -I http://localhost:8000/health

# Test frontend connectivity
curl -I https://yudai.app/health
```

## Summary

The production configuration has been successfully updated and tested. All services are properly configured with:

- ✅ Consistent API endpoints between dev and prod
- ✅ Proper SSL/TLS configuration
- ✅ Security headers and CORS settings
- ✅ Health checks and monitoring
- ✅ Error handling and fallbacks
- ✅ Environment-specific configurations

The setup is ready for production deployment with proper SSL certificates and environment variables. 