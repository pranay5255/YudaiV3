# YudaiV3 Deployment Guide

This guide provides step-by-step instructions for deploying YudaiV3 with Langfuse telemetry and testing the architect and daifu agents.

## Prerequisites

- Docker and Docker Compose
- OpenRouter API key
- GitHub OAuth credentials (optional)
- Basic understanding of environment variables

## Environment Setup

Create a `.env` file in the project root with the following variables:

```bash
# OpenRouter API for LLM access
OPENROUTER_API_KEY=your_openrouter_api_key_here

# GitHub OAuth credentials (optional for testing)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# Langfuse telemetry configuration
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_HOST=http://localhost:3000

# Langfuse Docker secrets
LANGFUSE_NEXTAUTH_SECRET=your-nextauth-secret-key-minimum-32-chars
LANGFUSE_ENCRYPTION_KEY=your-encryption-key-minimum-32-chars
```

## Quick Start with Bash Commands

### 1. Build and Deploy All Services

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd YudaiV3

# Create environment file
cp .env.example .env
# Edit .env with your actual API keys

# Build and start all services including Langfuse
docker compose up --build -d

# Check if all services are healthy
docker compose ps

# View logs for troubleshooting
docker compose logs -f backend
docker compose logs -f langfuse-web
```

### 2. Initialize Langfuse (First Time Setup)

```bash
# Wait for services to be ready (usually 2-3 minutes)
sleep 180

# Check Langfuse health
curl -f http://localhost:3000/api/public/health

# Open Langfuse UI in browser
echo "Open http://localhost:3000 in your browser to set up Langfuse"
echo "Create an account and project, then get your API keys"
```

### 3. Backend Health Check

```bash
# Check backend health
curl -f http://localhost:8000/health

# Check available endpoints
curl http://localhost:8000/docs
```

## Testing the Agents

### Test Architect Agent (GitHub Issue Generation)

```bash
# Test the architect agent for GitHub issue preview generation
curl -X POST "http://localhost:8000/api/issues/create-with-context?preview_only=true&use_sample_data=false" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "Add user authentication system",
    "description": "Implement secure user authentication with JWT tokens",
    "chat_messages": [
      {
        "id": "msg1",
        "content": "We need to add user authentication to our app",
        "isCode": false,
        "timestamp": "2025-01-11T10:00:00Z"
      },
      {
        "id": "msg2", 
        "content": "It should support JWT tokens and password hashing",
        "isCode": false,
        "timestamp": "2025-01-11T10:01:00Z"
      }
    ],
    "file_context": [
      {
        "id": "file1",
        "name": "auth.py",
        "type": "INTERNAL",
        "tokens": 150,
        "category": "authentication",
        "path": "backend/auth/auth.py"
      },
      {
        "id": "file2",
        "name": "models.py", 
        "type": "INTERNAL",
        "tokens": 300,
        "category": "database",
        "path": "backend/models.py"
      }
    ],
    "repository_info": {
      "owner": "test-owner",
      "name": "test-repo",
      "branch": "main"
    },
    "priority": "high"
  }'
```

### Test DaiFu User Agent

```bash
# Test DaiFu agent chat endpoint
curl -X POST "http://localhost:8000/api/daifu/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "conversationId": "test-conversation",
    "message": {
      "content": "Can you help me understand the codebase structure?",
      "is_code": false
    },
    "repoOwner": "test-owner",
    "repoName": "test-repo"
  }'

# Test DaiFu agent using simple GET endpoint
curl "http://localhost:8000/api/daifu/test?message=What%20can%20you%20tell%20me%20about%20this%20repository" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Testing Without Authentication (Development)

For testing purposes, you can temporarily disable authentication:

```bash
# Test architect agent without auth (if auth is disabled in dev)
curl -X POST "http://localhost:8000/api/issues/create-with-context?preview_only=true" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test issue",
    "description": "Testing the architect agent", 
    "chat_messages": [],
    "file_context": [],
    "priority": "medium"
  }'
```

## Monitoring and Telemetry

### Check Langfuse Dashboard

1. Open http://localhost:3000
2. Log in with your Langfuse credentials
3. Navigate to your project
4. View traces and metrics for:
   - Architect agent issue generations
   - DaiFu agent conversations
   - GitHub API calls
   - LLM usage statistics

### View Service Logs

```bash
# View backend logs
docker compose logs -f backend

# View Langfuse logs
docker compose logs -f langfuse-web

# View all services
docker compose logs -f
```

## Database Operations

```bash
# Access the main database
docker compose exec db psql -U yudai_user -d yudai_db

# Access Langfuse database
docker compose exec langfuse-db psql -U langfuse -d langfuse

# Backup database
docker compose exec db pg_dump -U yudai_user yudai_db > backup.sql
```

## Manual Testing Workflows

### Complete Issue Creation Workflow

```bash
# 1. Create issue preview
PREVIEW_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/issues/create-with-context?preview_only=true" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add dark mode support",
    "description": "Users want dark mode for better UX",
    "chat_messages": [{"id":"1","content":"Add dark mode","isCode":false,"timestamp":"2025-01-11T10:00:00Z"}],
    "file_context": [{"id":"1","name":"App.tsx","type":"INTERNAL","tokens":200,"category":"frontend"}],
    "priority": "medium"
  }')

echo "Preview Response: $PREVIEW_RESPONSE"

# 2. Create actual issue in database
curl -X POST "http://localhost:8000/api/issues/create-with-context" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add dark mode support",
    "description": "Users want dark mode for better UX",
    "chat_messages": [{"id":"1","content":"Add dark mode","isCode":false,"timestamp":"2025-01-11T10:00:00Z"}],
    "file_context": [{"id":"1","name":"App.tsx","type":"INTERNAL","tokens":200,"category":"frontend"}],
    "priority": "medium"
  }'

# 3. List created issues
curl "http://localhost:8000/api/issues/"
```

## Troubleshooting

### Common Issues

1. **Langfuse not starting**: Check if ClickHouse and Redis are healthy
2. **Backend connection errors**: Verify database connection and environment variables
3. **OpenRouter API errors**: Check your API key and quota
4. **Memory issues**: ClickHouse requires significant memory, ensure Docker has enough allocated

### Reset Everything

```bash
# Stop all services
docker compose down

# Remove volumes (WARNING: This deletes all data)
docker compose down -v

# Remove images
docker compose down --rmi all

# Start fresh
docker compose up --build -d
```

### Performance Optimization

```bash
# Monitor resource usage
docker stats

# Check disk usage
docker system df

# Clean up unused resources
docker system prune -f
```

## Production Deployment Notes

1. Change default passwords in production
2. Use proper SSL certificates
3. Set up backup procedures for databases
4. Monitor disk space for ClickHouse
5. Configure log rotation
6. Set up proper authentication and authorization
7. Use environment-specific configuration files

## API Documentation

Once deployed, access the interactive API documentation at:
- Backend API: http://localhost:8000/docs
- Langfuse API: http://localhost:3000/api/docs (if available)

## Support

If you encounter issues:
1. Check service logs: `docker compose logs <service-name>`
2. Verify environment variables are set correctly
3. Ensure all required ports are available
4. Check the Langfuse dashboard for telemetry data
5. Review the application logs for specific error messages 