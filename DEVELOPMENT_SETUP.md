# Development Setup Guide

## Quick Start

1. **Setup Environment Files**
   ```bash
   # Add your API keys to .env.dev.secrets
   # The .env.dev file is already configured for development
   ```

2. **Start Development Environment**
   ```bash
   docker compose -f docker-compose-dev.yml up -d
   ```

3. **View Logs**
   ```bash
   docker compose -f docker-compose-dev.yml logs -f
   ```

4. **Stop Environment**
   ```bash
   docker compose -f docker-compose-dev.yml down
   ```

## Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **Database**: localhost:5433 (yudai_dev, yudai_user, yudai_password)

**Note**: Development ports are different from production to avoid conflicts:
- Backend uses 8001 (instead of 8000)
- Database uses 5433 (instead of 5432)

## Required Setup

### 1. API Keys (.env.dev.secrets)
Add your actual API keys to `.env.dev.secrets`:

```bash
# OpenRouter
OPENROUTER_API_KEY=your_actual_openrouter_key

# GitHub App
GITHUB_APP_ID=your_github_app_id
GITHUB_APP_CLIENT_ID=your_github_app_client_id
GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret
GITHUB_APP_INSTALLATION_ID=your_github_app_installation_id
```

### 2. GitHub Private Key
Ensure you have the GitHub private key file:
```bash
./backend/yudaiv3.2025-08-02.private-key.pem
```

## Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Database | yudai_dev | ${POSTGRES_DB} |
| Debug Logging | Enabled | Disabled |
| Resource Limits | None | Strict limits |
| Security Hardening | Minimal | Full hardening |
| SSL | No | Yes |
| Hot Reload | Yes | No |
| Database Access | Direct (port 5432) | Internal only |

## Troubleshooting

### Check Service Health
```bash
docker compose -f docker-compose-dev.yml ps
```

### View Specific Service Logs
```bash
# Backend logs
docker compose -f docker-compose-dev.yml logs backend

# Database logs  
docker compose -f docker-compose-dev.yml logs db

# Frontend logs
docker compose -f docker-compose-dev.yml logs frontend
```

### Rebuild and Restart
```bash
docker compose -f docker-compose-dev.yml down
docker compose -f docker-compose-dev.yml up --build
```

### Clean Restart (fresh database)
```bash
docker compose -f docker-compose-dev.yml down -v
docker compose -f docker-compose-dev.yml up --build
```
