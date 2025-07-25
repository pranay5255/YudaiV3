# Langfuse Integration with YudaiV3

This document describes the integration of [Langfuse](https://langfuse.com/) with YudaiV3 for LLM observability, tracing, and evaluation.

## Overview

Langfuse is an open-source LLM observability platform that helps you:
- **Trace** LLM applications and chains
- **Debug** complex AI applications
- **Evaluate** model performance
- **Monitor** costs and usage
- **Optimize** prompts and models

## Architecture

The integration includes:

```
YudaiV3 Backend ──┐
                   ├── Langfuse Web UI (Port 3000)
YudaiV3 Frontend ──┤
                   ├── Langfuse Worker (Port 3030)
                   ├── PostgreSQL (Langfuse DB)
                   ├── ClickHouse (Analytics)
                   ├── Redis (Caching/Queues)
                   └── MinIO/S3 (Object Storage)
```

## Services

### Core Services
- **langfuse-web**: Web UI and API (Port 3000)
- **langfuse-worker**: Background processing (Port 3030)
- **postgres**: PostgreSQL database for Langfuse
- **clickhouse**: ClickHouse for analytical workloads
- **redis**: Redis for caching and queues
- **minio**: Object storage for backups and media

### YudaiV3 Services
- **backend**: YudaiV3 API server (Port 8000)
- **db**: YudaiV3 PostgreSQL database

## Quick Start

### 1. Setup Environment

Run the setup script to configure Langfuse:

```bash
./scripts/setup-langfuse.sh
```

This script will:
- Create a `.env` file from the template
- Generate secure encryption keys
- Configure object storage (local MinIO or external S3)
- Set up secure passwords for all services

### 2. Configure Object Storage

You have three options for object storage:

#### Option A: Local MinIO (Default)
- Data stored locally in Docker volumes
- MinIO API: `http://localhost:9090`
- MinIO Console: `http://localhost:9091`
- Default credentials: `minio` / `miniosecret`

#### Option B: External S3-Compatible Storage
Update your `.env` file with your S3 credentials:

```bash
# Example for AWS S3
LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=https://s3.amazonaws.com
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=your_access_key
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=your_secret_key
LANGFUSE_S3_EVENT_UPLOAD_REGION=us-east-1
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=your-bucket-name
LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=false
```

#### Option C: Skip Object Storage
Disable object storage features by setting:
```bash
LANGFUSE_S3_BATCH_EXPORT_ENABLED=false
```

### 3. Start Services

```bash
docker compose up -d
```

### 4. Access Applications

- **YudaiV3 Frontend**: http://localhost:5173
- **YudaiV3 Backend**: http://localhost:8000
- **Langfuse UI**: http://localhost:3000
- **MinIO Console**: http://localhost:9091 (if using local MinIO)

### 5. Initialize Langfuse

1. Visit http://localhost:3000
2. Create your first organization
3. Create your first project
4. Note down the project's public and secret keys

## Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Langfuse Core
LANGFUSE_ENCRYPTION_KEY=your-32-byte-hex-key
LANGFUSE_SALT=your-salt
LANGFUSE_NEXTAUTH_SECRET=your-nextauth-secret

# Database Passwords
CLICKHOUSE_PASSWORD=your-clickhouse-password
REDIS_AUTH=your-redis-password

# Object Storage
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_BATCH_EXPORT_BUCKET=langfuse
```

### Backend Integration

The YudaiV3 backend is configured to send telemetry to Langfuse:

```python
# In your backend code
import os

LANGFUSE_SECRET_KEY = os.getenv('LANGFUSE_SECRET_KEY')
LANGFUSE_PUBLIC_KEY = os.getenv('LANGFUSE_PUBLIC_KEY')
LANGFUSE_HOST = os.getenv('LANGFUSE_HOST', 'http://langfuse-web:3000')
```

## Usage

### Tracing LLM Calls

```python
from langfuse import Langfuse

# Initialize Langfuse client
langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="http://localhost:3000"
)

# Trace an LLM generation
trace = langfuse.trace(
    name="chat-completion",
    user_id="user-123"
)

generation = trace.generation(
    name="openai-chat",
    model="gpt-4",
    prompt="What is the capital of France?",
    completion="The capital of France is Paris.",
    metadata={"temperature": 0.7}
)

trace.update(status="success")
```

### Evaluation

```python
# Evaluate a generation
score = trace.score(
    name="relevance",
    value=0.95,
    comment="Highly relevant response"
)
```

### Span Tracking

```python
# Track spans for complex operations
with trace.span(name="data-processing") as span:
    # Your processing logic here
    span.update(metadata={"processed_items": 100})
```

## Data Storage

### Local Storage
- **PostgreSQL**: Langfuse metadata and user data
- **ClickHouse**: Analytics and traces
- **Redis**: Caching and job queues
- **MinIO**: Object storage for backups and media

### External Storage
When using external S3-compatible storage:
- **Events**: Stored in `events/` prefix
- **Media**: Stored in `media/` prefix  
- **Exports**: Stored in `exports/` prefix

## Backup and Recovery

### Automated Backups
Langfuse automatically exports data to object storage:
- **Batch exports**: Enabled by default
- **Event uploads**: Real-time event streaming
- **Media uploads**: File and image storage

### Manual Backups
```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U postgres postgres > backup.sql

# Backup ClickHouse
docker compose exec clickhouse clickhouse-client --query "BACKUP TABLE default.* TO '/backup'"

# Backup MinIO data
docker compose exec minio mc mirror /data /backup
```

## Monitoring

### Health Checks
All services include health checks:
- **langfuse-web**: `http://localhost:3000/api/public/health`
- **backend**: `http://localhost:8000/health`
- **postgres**: Database connectivity
- **clickhouse**: HTTP ping endpoint
- **redis**: Redis ping command
- **minio**: MinIO client ready check

### Logs
```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f langfuse-web
docker compose logs -f langfuse-worker
```

## Troubleshooting

### Common Issues

#### 1. Langfuse Web Not Starting
```bash
# Check logs
docker compose logs langfuse-web

# Verify dependencies
docker compose ps
```

#### 2. Object Storage Issues
```bash
# Test MinIO connectivity
curl http://localhost:9090/minio/health/live

# Check MinIO console
open http://localhost:9091
```

#### 3. Database Connection Issues
```bash
# Check PostgreSQL
docker compose exec postgres pg_isready -U postgres

# Check ClickHouse
curl http://localhost:8123/ping
```

### Reset Everything
```bash
# Stop and remove all containers and volumes
docker compose down -v

# Rebuild and start
docker compose up -d --build
```

## Security

### Default Credentials
⚠️ **Important**: Change all default credentials in production:

- **PostgreSQL**: `postgres` / `postgres`
- **ClickHouse**: `clickhouse` / `clickhouse`
- **Redis**: `myredissecret`
- **MinIO**: `minio` / `miniosecret`

### Network Security
- Only ports 3000 (Langfuse) and 9090 (MinIO) are exposed externally
- All other services are bound to localhost only
- Use reverse proxy for production deployments

## Production Deployment

### Recommendations
1. **Use external databases** for production
2. **Configure external object storage** (AWS S3, etc.)
3. **Set up proper SSL/TLS** termination
4. **Configure backups** and monitoring
5. **Use secrets management** for credentials

### Scaling
- **Horizontal scaling**: Use Kubernetes deployment
- **Vertical scaling**: Increase container resources
- **Database scaling**: Use managed PostgreSQL/ClickHouse

## Support

- **Langfuse Documentation**: https://langfuse.com/docs
- **Langfuse GitHub**: https://github.com/langfuse/langfuse
- **YudaiV3 Issues**: Create an issue in the YudaiV3 repository

## License

Langfuse is licensed under the MIT License. See the [Langfuse repository](https://github.com/langfuse/langfuse) for details. 