# Vercel Frontend + Docker Compose Backend Deployment

This guide uses a single production architecture:
- **Frontend**: Vercel (from `src/`)
- **Backend**: Docker Compose on your server
- **API routing**: Frontend calls backend directly via `https://api.yudai.app`

---

## Deployment Architecture

| Layer | Endpoint | Notes |
|------|----------|-------|
| Frontend | `https://yudai.app` | Hosted on Vercel |
| Backend API | `https://api.yudai.app` | Public HTTPS endpoint to your backend host |

Important:
1. Keep `src/vercel.json` free of `/api` rewrites to raw IP addresses.
2. Set `VITE_API_BASE_URL=https://api.yudai.app` in Vercel production env vars.
3. Set backend `BACKEND_URL=https://api.yudai.app`.
4. Backend serves canonical routes only (no `/api/*` compatibility aliases).
5. If you use `VITE_WS_BASE_URL=ws://...`, note that browsers often block insecure WS from `https://` frontends.

---

## Step 1: Prepare Environment

```bash
# From project root
cp .env.deploy.template .env.deploy
cp .env.prod backend/.env.prod
```

Set these values in `backend/.env.prod`:
- `ALLOW_ORIGINS=https://yudai.app`
- `ALLOW_ORIGIN_REGEX=^https://.*\.vercel\.app$`
- `FRONTEND_URL=https://yudai.app`
- `BACKEND_URL=https://api.yudai.app`
- `GITHUB_REDIRECT_URI=https://yudai.app/auth/callback`

---

## Step 2: Deploy Backend

```bash
# From project root
docker compose -f docker-compose.backend-only.yml up -d --build
```

Check status:

```bash
docker compose -f docker-compose.backend-only.yml ps
docker compose -f docker-compose.backend-only.yml logs -f backend
curl http://localhost:8000/health
```

---

## Step 3: Deploy Frontend on Vercel

```bash
cd src
vercel --prod
```

Set Vercel production env vars:

```bash
VITE_API_BASE_URL=https://api.yudai.app
VITE_WS_BASE_URL=ws://139.84.154.9:8000
VITE_REALTIME_CONTROLLER_SPLIT_ENABLED=true
VITE_REALTIME_CONTROLLER_PROXY_ENABLED=true
VITE_REALTIME_WS_UNIFIED_ENABLED=true
```

CLI alternative:

```bash
cd src
vercel env add VITE_API_BASE_URL production
# Enter: https://api.yudai.app
vercel --prod
```

---

## Step 4: Configure DNS

Add DNS records:

| Record | Type | Value |
|--------|------|-------|
| `yudai.app` | A | 76.76.21.21 |
| `api.yudai.app` | A | YOUR_SERVER_IP |

---

## Quick Deploy

```bash
./scripts/deploy.sh \
  --backend-domain api.yudai.app \
  --frontend-domain yudai.app
```

With Vercel token:

```bash
./scripts/deploy.sh \
  --backend-domain api.yudai.app \
  --frontend-domain yudai.app \
  --vercel-token your_vercel_token
```

---

## Validation Checklist

```bash
# Backend public health endpoint
curl https://api.yudai.app/health

# Frontend
curl https://yudai.app
```

For WebSocket endpoints:

```bash
npm install -g wscat
wscat -c ws://139.84.154.9:8000/controller/sessions/test-session/ws/unified?token=test-token
```

---

## Troubleshooting

Backend checks:

```bash
docker logs yudai-be
docker compose -f docker-compose.backend-only.yml restart backend
```

Common issues:
1. `403`/CORS: ensure `ALLOW_ORIGINS` and `ALLOW_ORIGIN_REGEX` are set correctly.
2. OAuth callback mismatch: ensure `GITHUB_REDIRECT_URI=https://yudai.app/auth/callback`.
3. Frontend calling wrong host: verify Vercel `VITE_API_BASE_URL=https://api.yudai.app`.
