# Production Connectivity Tests

This directory contains comprehensive tests to verify frontend-to-backend communication in your production environment.

## Overview

The tests are designed to verify that your production setup with Docker Compose is working correctly, specifically:

- **Frontend-to-backend communication** via nginx proxy
- **SSL/TLS configuration** and security headers
- **CORS setup** for cross-origin requests
- **API endpoint accessibility** through both main domain and API subdomain
- **Docker container health** and internal networking
- **Database connectivity** from the backend
- **Performance metrics** and response times

## Test Files

### 1. TypeScript Tests (`prod-connectivity.test.ts`)
Comprehensive TypeScript tests using Vitest and Axios to test external connectivity.

**Tests include:**
- Main domain frontend serving
- API proxy functionality via `/api/` path
- Direct API subdomain access
- CORS preflight requests
- SSL/TLS configuration
- Security headers
- Load testing and performance

### 2. Shell Script Tests (`test-prod-connectivity.sh`)
External connectivity tests using curl and shell commands.

**Tests include:**
- HTTP to HTTPS redirects
- SSL certificate validation
- Response time measurements
- Concurrent request handling
- Basic API endpoint testing

### 3. Docker Environment Tests (`docker-prod-test.sh`)
Internal Docker network tests to verify container-to-container communication.

**Tests include:**
- Container health checks
- Internal network connectivity
- Database connectivity from backend
- Volume mount verification
- Environment variable validation
- Performance testing within Docker network

## Running the Tests

### Prerequisites

1. **Production environment running:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

2. **Dependencies installed:**
   ```bash
   npm install
   ```

3. **SSL certificates configured** (for external tests)

### Test Commands

#### Run All Tests
```bash
npm run test:prod
```

#### Run Specific Test Types

**TypeScript tests only:**
```bash
npm run test:prod:typescript
# or
npm run test:connectivity
```

**External connectivity tests only:**
```bash
npm run test:prod:external
```

**Docker environment tests only:**
```bash
npm run test:prod:docker
```

#### Manual Test Execution

**TypeScript tests:**
```bash
npm test tests/prod-connectivity.test.ts
```

**Shell script tests:**
```bash
bash scripts/test-prod-connectivity.sh
```

**Docker tests:**
```bash
bash tests/docker-prod-test.sh
```

**Test runner with options:**
```bash
bash scripts/run-tests.sh --help
bash scripts/run-tests.sh --verbose
bash scripts/run-tests.sh --typescript-only
```

## Test Configuration

### Environment Variables

The tests use the following configuration:

- **Main Domain:** `https://yudai.app`
- **API Subdomain:** `https://api.yudai.app`
- **Backend Service:** `backend:8000` (internal Docker network)
- **Database Service:** `db:5432` (internal Docker network)

### Test Endpoints

The tests verify these key endpoints:

- `/health` - Health check endpoint
- `/docs` - API documentation
- `/api/*` - API proxy via main domain
- `/` - Frontend application

## Understanding Test Results

### ✅ Success Indicators

- **HTTP 200/204 responses** for health checks and CORS preflight
- **HTTP 301 redirects** for HTTP to HTTPS
- **Valid SSL certificates** with proper TLS versions
- **Security headers** present (HSTS, X-Frame-Options, etc.)
- **CORS headers** allowing requests from main domain
- **Response times** under 2 seconds
- **Container health** status showing "healthy"

### ❌ Common Failure Points

1. **SSL Certificate Issues:**
   - Invalid or expired certificates
   - Missing intermediate certificates
   - Wrong domain names

2. **Nginx Configuration:**
   - Incorrect proxy_pass settings
   - Missing CORS headers
   - Wrong server_name directives

3. **Docker Issues:**
   - Containers not running
   - Network connectivity problems
   - Volume mount failures

4. **Backend Issues:**
   - Service not responding on port 8000
   - Database connection failures
   - Environment variable misconfiguration

## Troubleshooting

### If External Tests Fail

1. **Check SSL certificates:**
   ```bash
   openssl s_client -connect yudai.app:443 -servername yudai.app
   ```

2. **Verify nginx configuration:**
   ```bash
   docker exec yudai-fe nginx -t
   ```

3. **Check container logs:**
   ```bash
   docker logs yudai-fe
   docker logs yudai-be
   ```

### If Docker Tests Fail

1. **Check container status:**
   ```bash
   docker ps
   docker ps -a
   ```

2. **Verify network connectivity:**
   ```bash
   docker network inspect yudai-network
   ```

3. **Test internal connectivity:**
   ```bash
   docker exec yudai-fe curl http://backend:8000/health
   ```

### If TypeScript Tests Fail

1. **Check network connectivity:**
   ```bash
   curl -I https://yudai.app
   curl -I https://api.yudai.app/health
   ```

2. **Verify CORS headers:**
   ```bash
   curl -H "Origin: https://yudai.app" -H "Access-Control-Request-Method: GET" \
        -X OPTIONS https://api.yudai.app/health
   ```

## GitHub OAuth Configuration

For GitHub authentication to work properly, ensure your GitHub OAuth App is configured with:

**Authorization callback URL:** `https://yudai.app/auth/callback`

This matches the `GITHUB_REDIRECT_URI` environment variable in your `docker-compose.prod.yml`.

## Continuous Integration

You can integrate these tests into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Test Production Connectivity
  run: |
    npm run test:prod:typescript
    npm run test:prod:docker
```

## Performance Benchmarks

The tests include performance benchmarks:

- **Response time:** < 2 seconds for health checks
- **Concurrent requests:** 5 simultaneous requests should all succeed
- **Average response time:** < 1 second under load

## Security Considerations

The tests verify:

- **HTTPS enforcement** via HSTS headers
- **CORS configuration** to prevent unauthorized cross-origin requests
- **Security headers** (X-Frame-Options, X-Content-Type-Options, etc.)
- **SSL/TLS configuration** with modern protocols

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Include proper error handling
3. Add descriptive test names and comments
4. Update this README with new test information
5. Ensure tests work in both development and production environments 