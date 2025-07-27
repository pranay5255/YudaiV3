# YudaiV3 Backend API

A unified FastAPI server that combines all backend services for the YudaiV3 application.

## Services Included

### 🔐 Authentication (`/auth`)
- GitHub OAuth authentication
- User session management
- Profile management

### 🐙 GitHub Integration (`/github`)
- Repository management
- Issue creation and management
- Pull request handling
- Repository search

### 💬 Chat Services (`/daifu`)
- DAifu AI agent integration
- Chat session management
- Message history
- Issue creation from chat

### 📋 Issue Management (`/issues`)
- User issue creation and management
- Issue status tracking
- GitHub issue conversion
- Issue statistics

### 📁 File Dependencies (`/filedeps`)
- Repository file structure extraction
- File dependency analysis
- GitIngest integration
- File categorization

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database
- GitHub OAuth app configured

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your configuration
```

3. Initialize the database:
```bash
python init_db.py
```

4. Start the server:
```bash
python run_server.py
```

The server will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Production Deployment

### Docker Compose Production Setup

The production environment uses Docker Compose with the following services:

#### 1. Database Service (`db`)
- **Container**: `yudai-db`
- **Port**: Internal only (5432)
- **Health Check**: PostgreSQL readiness check
- **Volumes**: Persistent PostgreSQL data

#### 2. Backend Service (`backend`)
- **Container**: `yudai-be`
- **Port**: 127.0.0.1:8000 (localhost only)
- **Health Check**: HTTP health endpoint
- **Environment Variables**:
  - `DATABASE_URL`: PostgreSQL connection string
  - `GITHUB_CLIENT_ID`: GitHub OAuth app client ID
  - `GITHUB_CLIENT_SECRET`: GitHub OAuth app client secret
  - `GITHUB_REDIRECT_URI`: https://yudai.app/auth/callback
  - `API_DOMAIN`: api.yudai.app
  - `DEV_DOMAIN`: dev.yudai.app

#### 3. Frontend Service (`frontend`)
- **Container**: `yudai-fe`
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Environment Variables**:
  - `VITE_API_URL`: https://yudai.app/api
- **SSL**: Mounted from `./ssl` directory
- **Health Check**: Frontend health endpoint

### Nginx Configuration

The production setup uses nginx as a reverse proxy with SSL termination. There are two nginx configuration files:

#### `nginx.prod.conf` - Production Configuration
- **SSL/TLS**: Full SSL configuration with modern ciphers
- **Multiple Domains**: 
  - `yudai.app` (main application)
  - `api.yudai.app` (API subdomain)
  - `dev.yudai.app` (development subdomain)
- **Security Headers**: HSTS, X-Frame-Options, CSP, etc.
- **CORS**: Configured for cross-origin requests
- **Proxy Rules**:
  - `/auth/*` → `backend:8000/auth/*` (direct auth proxy)
  - `/api/*` → `backend:8000/*` (API proxy with prefix removal)
  - `/` → Static frontend files

#### `nginx.conf` - Development Configuration
- **HTTP Only**: No SSL configuration
- **Single Domain**: localhost
- **Simplified CORS**: Allow all origins (`*`)
- **Proxy Rules**:
  - `/auth/*` → `backend:8000/auth/*`
  - `/api/*` → `backend:8000/*`

### Production Deployment Commands

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

## API Endpoints

### Root Endpoints
- `GET /` - API information and service overview
- `GET /health` - Health check

### Authentication (`/auth`)
- `GET /auth/login` - GitHub OAuth login (redirects to GitHub)
- `GET /auth/callback` - OAuth callback (handles GitHub response)
- `GET /auth/profile` - User profile (requires authentication)
- `POST /auth/logout` - Logout (requires authentication)
- `GET /auth/status` - Auth status (optional authentication)
- `GET /auth/config` - Auth configuration (public)

### GitHub Integration (`/github`)
- `GET /github/repositories` - User repositories (requires auth)
- `GET /github/repositories/{owner}/{repo}` - Repository details
- `POST /github/repositories/{owner}/{repo}/issues` - Create issue
- `GET /github/repositories/{owner}/{repo}/issues` - Repository issues
- `GET /github/repositories/{owner}/{repo}/pulls` - Repository PRs
- `GET /github/repositories/{owner}/{repo}/commits` - Repository commits
- `GET /github/search/repositories` - Search repositories

### Chat Services (`/daifu`)
- `POST /daifu/chat/daifu` - Chat with DAifu agent (requires auth)
- `GET /daifu/chat/sessions` - Chat sessions (requires auth)
- `GET /daifu/chat/sessions/{session_id}/messages` - Session messages
- `GET /daifu/chat/sessions/{session_id}/statistics` - Session statistics
- `PUT /daifu/chat/sessions/{session_id}/title` - Update session title
- `DELETE /daifu/chat/sessions/{session_id}` - Deactivate session
- `POST /daifu/chat/create-issue` - Create issue from chat

### Issue Management (`/issues`)
- `POST /issues/` - Create user issue (requires auth)
- `GET /issues/` - Get user issues (requires auth)
- `GET /issues/{issue_id}` - Get specific issue
- `PUT /issues/{issue_id}/status` - Update issue status
- `POST /issues/{issue_id}/convert-to-github` - Convert to GitHub issue
- `POST /issues/from-chat` - Create issue from chat
- `GET /issues/statistics` - Issue statistics

### File Dependencies (`/filedeps`)
- `GET /filedeps/` - File dependencies API info
- `GET /filedeps/repositories` - User repositories (requires auth)
- `GET /filedeps/repositories?repo_url=<url>` - Repository lookup by URL
- `GET /filedeps/repositories/{repository_id}` - Repository details
- `GET /filedeps/repositories/{repository_id}/files` - Repository files
- `POST /filedeps/extract` - Extract file dependencies

## Frontend Integration

### Environment Variables
- `VITE_API_URL`: Base URL for API requests
  - Development: `http://localhost:8000`
  - Production: `https://yudai.app/api`

### Authentication Flow
1. User clicks login → `GET /auth/login`
2. Redirected to GitHub OAuth
3. GitHub redirects to → `GET /auth/callback?code=...&state=...`
4. Backend exchanges code for token
5. Frontend stores token in localStorage
6. Subsequent requests include `Authorization: Bearer <token>` header

### API Request Patterns
```javascript
// Auth endpoints (direct proxy)
const authUrl = `${API_BASE_URL}/auth/login`;

// API endpoints (with /api prefix)
const apiUrl = `${API_BASE_URL}/github/repositories`;
```

## Environment Variables

### Required Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `GITHUB_CLIENT_ID` - GitHub OAuth app client ID
- `GITHUB_CLIENT_SECRET` - GitHub OAuth app client secret
- `GITHUB_REDIRECT_URI` - OAuth redirect URI
- `OPENROUTER_API_KEY` - OpenRouter API key for DAifu agent
- `SECRET_KEY` - Application secret key
- `JWT_SECRET` - JWT token signing secret

### Production-Specific Variables
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `API_DOMAIN` - API subdomain (api.yudai.app)
- `DEV_DOMAIN` - Development subdomain (dev.yudai.app)

## Security Configuration

### SSL/TLS
- **Protocols**: TLSv1.2, TLSv1.3
- **Ciphers**: Modern ECDHE-RSA ciphers
- **HSTS**: 1 year with includeSubDomains
- **Certificate**: Full chain required

### Security Headers
- `Strict-Transport-Security`: HTTPS enforcement
- `X-Frame-Options`: Clickjacking protection
- `X-Content-Type-Options`: MIME type sniffing protection
- `X-XSS-Protection`: XSS protection
- `Referrer-Policy`: Referrer information control

### CORS Configuration
- **Allowed Origins**: https://yudai.app
- **Methods**: GET, POST, PUT, DELETE, OPTIONS
- **Headers**: Authorization, Content-Type, etc.
- **Credentials**: Supported

## Error Handling

All endpoints include proper error handling with appropriate HTTP status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

## Health Checks

### Container Health Checks
- **Database**: PostgreSQL readiness check
- **Backend**: HTTP health endpoint
- **Frontend**: Nginx health endpoint

### Health Endpoints
- `GET /health` - Backend health check
- `GET /` - Frontend health check (nginx)

## Monitoring and Logging

### Nginx Logs
- **Access Logs**: Request/response logging
- **Error Logs**: Error condition logging
- **Format**: JSON format for production

### Application Logs
- **Backend**: FastAPI application logs
- **Database**: PostgreSQL logs
- **Container**: Docker container logs

## Development vs Production

### Development Environment
- **File**: `docker-compose.yml`
- **Nginx**: `nginx.conf`
- **SSL**: Disabled
- **CORS**: Allow all origins
- **Ports**: Exposed directly

### Production Environment
- **File**: `docker-compose.prod.yml`
- **Nginx**: `nginx.prod.conf`
- **SSL**: Enabled with certificates
- **CORS**: Restricted to specific domains
- **Ports**: Internal networking with nginx proxy

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

