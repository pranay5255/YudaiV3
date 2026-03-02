# Vercel Frontend + Separate Backend Deployment

This project can run with:

- Frontend on Vercel
- Backend (`backend/run_controller.py`) on a separate server (`139.84.154.9`)

## Frontend (Vercel)

Recommended frontend env vars:

- `VITE_API_BASE_URL=/api`
- `VITE_REALTIME_CONTROLLER_SPLIT_ENABLED=true`
- `VITE_REALTIME_CONTROLLER_PROXY_ENABLED=true`
- `VITE_REALTIME_WS_UNIFIED_ENABLED=true` (if you are using unified WS)

`vercel.json` rewrites `/api/*` to:

- `http://139.84.154.9:8000/*`

That keeps browser requests same-origin (`https://your-app.vercel.app/api/...`) while Vercel proxies to the backend server.

Repository layout note:

- Frontend is now a standalone app in `src/`
- Set Vercel project Root Directory to `src`
- Keep the rewrite config in `src/vercel.json`
- Local build command: `cd src && npm run build`

## Backend Server (139.84.154.9)

Run the controller host (from repo root or by `cd backend`):

```bash
cd backend
uvicorn run_controller:app --host 0.0.0.0 --port 8000
```

Key env vars:

- `DATABASE_URL=...`
- `ALLOW_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com`
- `ALLOW_ORIGIN_REGEX=^https://.*\\.vercel\\.app$` (optional; helps preview deployments)

## Validation Checklist

1. `GET https://<your-vercel-domain>/api/health` returns backend health.
2. Create a session from the frontend and confirm the response includes `runtime_id` / `sandbox_id` when realtime rollout is enabled.
3. If using controller proxy mode, confirm session requests route through `/api/controller/proxy/...`.
4. If using unified WebSocket mode, verify `/api/controller/proxy/sessions/{sessionId}/ws/...` works end-to-end.

## Important TLS / WS Note

If you point the browser directly to `http://139.84.154.9:8000` from a Vercel HTTPS site, browsers may block requests (mixed content), especially WebSockets.

Using the Vercel `/api` rewrite avoids that for HTTP requests. For WebSockets, test your exact Vercel setup; if proxying WS is unreliable, put a TLS reverse proxy (Nginx/Caddy) in front of the backend and use an HTTPS backend domain.
