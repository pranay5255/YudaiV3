# Vercel Frontend + Docker Compose Backend Deployment

This guide covers deploying:
- **Frontend**: Vercel (from `src/`)
- **Backend**: Docker Compose (from project root)

---

## Deployment Modes

| Mode | Architecture | WebSocket Support | Complexity |
|------|-------------|-------------------|------------|
| **nginx** (recommended) | Frontend → Vercel → Nginx (SSL) → Backend | ✅ Full support with long timeouts | Medium |
| **direct** | Frontend → Vercel rewrite → Backend IP | ⚠️ Limited by Vercel timeouts | Low |

**For WebSocket-based APIs, use nginx mode** - Vercel serverless functions have timeout limits (typically 10-30 seconds on free/pro plans) that will disconnect long-running WebSocket sessions.

---

## WebSocket vs HTTP: Key Differences

Understanding why nginx mode is recommended for WebSockets:

| Aspect | HTTP | WebSocket |
|--------|------|-----------|
| **Connection** | Request-response, then closes | Persistent, bidirectional |
| **Timeout** | Typically 30-60 seconds | Can run for hours |
| **Headers** | Standard headers | `Upgrade: websocket`, `Connection: upgrade` |
| **CORS** | Preflight OPTIONS requests | No preflight, but origin check |
| **Proxy** | Simple HTTP proxy | Must support `Upgrade` header |

### WebSocket-Specific Nginx Settings

The nginx config includes critical WebSocket support:

```nginx
# Enable WebSocket upgrade
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Long timeouts for persistent connections (24 hours)
proxy_read_timeout 86400s;
proxy_send_timeout 86400s;

# Special location for WebSocket endpoints
location ~ ^/controller/sessions/.*/ws/ {
    proxy_pass http://backend_upstream;
    proxy_read_timeout 86400s;
}
```

---

## Step 1: Prepare Environment

### 1a. Copy environment template:

```bash
# From project root
cp .env.deploy.template .env.deploy
cp .env.prod backend/.env.prod
```

### 1b. Key environment variables in `backend/.env.prod`:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ALLOW_ORIGINS` | Frontend domains (e.g., `https://yudai.app`) |
| `ALLOW_ORIGIN_REGEX` | Preview deployments (e.g., `^https://.*\.vercel\.app$`) |
| `FRONTEND_URL` | Your frontend URL |
| `BACKEND_URL` | Your backend URL (e.g., `https://api.yudai.app`) |
| `GITHUB_REDIRECT_URI` | GitHub OAuth callback URL |

---

## Step 2: Deploy Backend with Docker Compose

### 2a. Verify Docker and Docker Compose:

```bash
docker --version
docker compose version
```

### 2b. Build and start backend:

```bash
# From project root
docker compose -f docker-compose.backend-only.yml up -d --build
```

### 2c. Check containers:

```bash
docker compose -f docker-compose.backend-only.yml ps
```

### 2d. View logs:

```bash
docker compose -f docker-compose.backend-only.yml logs -f backend
```

### 2e. Verify health:

```bash
curl http://localhost:8000/health
```

---

## Step 3: Deploy Backend Proxy (nginx mode)

### 3a. Install nginx and certbot:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install nginx certbot python3-certbot-nginx
```

### 3b. Copy nginx configuration:

```bash
sudo cp nginx/api.yudai.app.conf /etc/nginx/sites-available/api.yudai.app
sudo ln -s /etc/nginx/sites-available/api.yudai.app /etc/nginx/sites-enabled/
```

### 3c. Edit domain placeholders:

```bash
sudo nano /etc/nginx/sites-available/api.yudai.app
# Replace:
#   BACKEND_DOMAIN -> api.yudai.app
#   FRONTEND_DOMAIN -> yudai.app
```

### 3d. Test and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3e. Obtain SSL certificate:

```bash
sudo certbot --nginx -d api.yudai.app --non-interactive --agree-tos --email your@email.com
```

### 3f. Verify HTTPS works:

```bash
curl https://api.yudai.app/health
```

---

## Step 4: Deploy Frontend on Vercel

### 4a. Install Vercel CLI:

```bash
npm install -g vercel
vercel login
```

### 4b. Deploy from `src/`:

```bash
cd src
vercel --prod
```

### 4c. Set environment variables in Vercel dashboard:

Go to Settings → Environment Variables:

```
VITE_API_BASE_URL=https://api.yudai.app
VITE_REALTIME_CONTROLLER_SPLIT_ENABLED=true
VITE_REALTIME_CONTROLLER_PROXY_ENABLED=true
VITE_REALTIME_WS_UNIFIED_ENABLED=true
```

### 4d. Alternative: Set env vars via CLI:

```bash
cd src
vercel env add VITE_API_BASE_URL production
# Enter: https://api.yudai.app

vercel env add VITE_REALTIME_CONTROLLER_SPLIT_ENABLED production
# Enter: true

vercel --prod
```

---

## Step 5: Configure DNS

Add DNS records:

| Record | Type | Value |
|--------|------|-------|
| `yudai.app` | A | 76.76.21.21 (Vercel) |
| `api.yudai.app` | A | YOUR_SERVER_IP |

---

## Quick Deploy (Recommended: nginx mode)

### Using the deploy script:

```bash
# Full deployment with nginx mode
./scripts/deploy.sh \
  --mode nginx \
  --backend-domain api.yudai.app \
  --frontend-domain yudai.app \
  --ssl-email admin@yudai.app

# Or with Vercel token for CI/CD
./scripts/deploy.sh \
  --mode nginx \
  --backend-domain api.yudai.app \
  --frontend-domain yudai.app \
  --ssl-email admin@yudai.app \
  --vercel-token your_vercel_token
```

### Manual step-by-step:

```bash
# 1. Backend
docker compose -f docker-compose.backend-only.yml up -d --build

# 2. Nginx
sudo cp nginx/api.yudai.app.conf /etc/nginx/sites-available/
# Edit domains, then:
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.yudai.app

# 3. Frontend
cd src
vercel --prod --env VITE_API_BASE_URL=https://api.yudai.app
```

---

## Validation Checklist

### 5a. Test backend HTTP:

```bash
curl https://api.yudai.app/health
```

### 5b. Test WebSocket connection:

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket
wscat -c wss://api.yudai.app/api/controller/proxy/sessions/test-session/ws
```

### 5c. Test through Vercel:

```bash
curl https://your-vercel-domain/api/health
```

### 5d. Check browser WebSocket:

Open DevTools → Network → filter WS → connect to `/api/controller/proxy/sessions/.../ws`

---

## Troubleshooting

### Backend Issues

```bash
docker logs yudai-be
docker ps | grep yudai
docker compose -f docker-compose.backend-only.yml restart backend
```

### Nginx Issues

```bash
# Check nginx error logs
sudo tail -f /var/log/nginx/yudai-api.error.log

# Test config
sudo nginx -t

# Reload
sudo systemctl reload nginx
```

### WebSocket Issues

```bash
# Test WebSocket directly
wscat -c ws://localhost:8000/api/controller/proxy/sessions/test/ws

# Test through nginx
wscat -c wss://api.yudai.app/api/controller/proxy/sessions/test/ws

# Check nginx WebSocket headers
curl -I -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  https://api.yudai.app/health
```

### Common WebSocket Problems

1. **Connection timeout**: Use nginx mode with long timeouts
2. **Mixed content**: Use `wss://` not `ws://` (nginx provides HTTPS)
3. **CORS error**: Check `ALLOW_ORIGINS` includes your domain
4. **Vercel limits**: If using direct mode, Vercel will timeout long connections

---

## Direct Mode (Not Recommended for WebSockets)

If you must use direct mode (no nginx):

```bash
# Update vercel.json
cd src
nano vercel.json
```

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "http://139.84.154.9:8000/:path*" }
  ]
}
```

Set env var: `VITE_API_BASE_URL=/api`

**Limitation**: WebSocket connections will be limited by Vercel's timeout (typically 10-30 seconds).
