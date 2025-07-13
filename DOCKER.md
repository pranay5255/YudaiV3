# Docker Setup for YudaiV3

This document describes how to set up and run YudaiV3 using Docker containers.

## Architecture

The application consists of three main services:

1. **Frontend** (React + Vite + Nginx) - Port 80
2. **Backend** (FastAPI + Python) - Port 8000  
3. **Database** (PostgreSQL) - Port 5432

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)
- At least 2GB of available RAM

## Quick Start

### Production Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd YudaiV3
   ```

2. **Build and run all services**
   ```bash
   docker-compose up -d
   ```

3. **Initialize the database**
   ```bash
   docker-compose exec backend python db/init_db.py --init
   ```

4. **Access the application**
   - Frontend: http://localhost
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Development Setup

1. **Use the development compose file**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Initialize the database**
   ```bash
   docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --init
   ```

3. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql://yudai_user:yudai_password@db:5432/yudai_db
DB_ECHO=false

# PostgreSQL Database
POSTGRES_DB=yudai_db
POSTGRES_USER=yudai_user
POSTGRES_PASSWORD=yudai_password

# GitHub OAuth (to be implemented)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_CALLBACK_URL=http://localhost:8000/auth/github/callback

# JWT Configuration (to be implemented)
JWT_SECRET_KEY=your_jwt_secret_key_change_this_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Frontend Configuration
VITE_API_URL=http://localhost:8000

# Development
NODE_ENV=development
PYTHONPATH=/app
```

## Database

### Database Schema

The database includes the following tables:

- `users` - User authentication and profile information
- `auth_tokens` - GitHub OAuth tokens
- `repositories` - Repository metadata and processing results
- `file_items` - Individual files from repository analysis
- `context_cards` - User-created context cards
- `idea_items` - Ideas and feature requests

### Database Management

**Initialize database:**
```bash
docker-compose exec backend python db/init_db.py --init
```

**Check database health:**
```bash
docker-compose exec backend python db/init_db.py --check
```

**Connect to database:**
```bash
docker-compose exec db psql -U yudai_user -d yudai_db
```

**Backup database:**
```bash
docker-compose exec db pg_dump -U yudai_user yudai_db > backup.sql
```

**Restore database:**
```bash
docker-compose exec -T db psql -U yudai_user -d yudai_db < backup.sql
```

## Service Management

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d backend

# View logs
docker-compose logs -f backend
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Rebuilding Services

```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build backend

# Rebuild and restart
docker-compose up -d --build
```

## Development

### Backend Development

The backend service includes hot-reloading in development mode. Changes to Python files will automatically restart the server.

**Access backend logs:**
```bash
docker-compose logs -f backend
```

**Run backend tests:**
```bash
docker-compose exec backend python -m pytest
```

**Access backend shell:**
```bash
docker-compose exec backend bash
```

### Frontend Development

In development mode, the frontend runs with Vite's development server with hot-reloading enabled.

**Access frontend logs:**
```bash
docker-compose -f docker-compose.dev.yml logs -f frontend
```

**Install frontend dependencies:**
```bash
docker-compose -f docker-compose.dev.yml exec frontend pnpm install
```

**Run frontend tests:**
```bash
docker-compose -f docker-compose.dev.yml exec frontend pnpm test
```

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Check if the database container is running: `docker-compose ps`
   - Check database logs: `docker-compose logs db`
   - Verify database is healthy: `docker-compose exec backend python db/init_db.py --check`

2. **Port conflicts**
   - Ensure ports 80, 8000, and 5432 are not in use
   - Modify ports in `docker-compose.yml` if needed

3. **Build failures**
   - Clear Docker cache: `docker system prune -a`
   - Rebuild without cache: `docker-compose build --no-cache`

4. **Permission issues**
   - Ensure Docker daemon is running
   - Check file permissions in the project directory

### Health Checks

All services include health checks. Check service health:

```bash
docker-compose ps
```

### Container Resource Usage

Monitor container resource usage:

```bash
docker stats
```

## Production Considerations

### Security

1. **Change default passwords** in production
2. **Use environment variables** for sensitive data
3. **Enable HTTPS** with proper SSL certificates
4. **Configure firewall** to restrict access
5. **Regular security updates** for base images

### Performance

1. **Scale services** using Docker Swarm or Kubernetes
2. **Use external database** for production workloads
3. **Implement caching** (Redis) for better performance
4. **Monitor logs** and metrics

### Backup

1. **Regular database backups**
2. **Volume backups** for persistent data
3. **Configuration backups**

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Support

For issues and questions:
1. Check the logs: `docker-compose logs`
2. Review this documentation
3. Check the main README.md for project-specific information 