# Development Workflow

This document outlines the development workflow for the YudaiV3 project, including how to set up development and production environments.

## Branch Structure

- `main` - Main branch, contains stable code
- `development` - Development branch for testing new features
- `production` - Production branch for deployment

## Environment Setup

### 1. Environment Files

The project uses different environment files for different environments:

- `.env.development` - Development environment (not committed to git)
- `.env.production` - Production environment (not committed to git)
- `.env.development.example` - Template for development environment
- `.env.production.example` - Template for production environment

### 2. Setting Up Environment Files

1. Copy the example files to create your environment files:
   ```bash
   cp .env.development.example .env.development
   cp .env.production.example .env.production
   ```

2. Edit the files with your actual values:
   - Database credentials
   - GitHub OAuth credentials
   - API keys
   - Security keys

### 3. Docker Compose Files

- `docker-compose.dev.yml` - Development environment
- `docker-compose.prod.yml` - Production environment

### 4. Nginx Configuration

- `nginx.dev.conf` - Development nginx configuration
- `nginx.prod.conf` - Production nginx configuration

## Development Workflow

### 1. Starting Development

1. Switch to development branch:
   ```bash
   git checkout development
   ```

2. Start development environment:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. Access the application:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

### 2. Making Changes

1. Create a feature branch from development:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and test them

3. Commit your changes:
   ```bash
   git add .
   git commit -m "Add feature description"
   ```

4. Push to your feature branch:
   ```bash
   git push origin feature/your-feature-name
   ```

5. Create a pull request to merge into development

### 3. Testing in Development

1. After merging to development, test your changes:
   ```bash
   git checkout development
   git pull origin development
   docker-compose -f docker-compose.dev.yml down
   docker-compose -f docker-compose.dev.yml up -d --build
   ```

2. Verify everything works correctly

### 4. Deploying to Production

1. When ready for production, merge development to production:
   ```bash
   git checkout production
   git merge development
   git push origin production
   ```

2. Deploy to production:
   ```bash
   ./scripts/deploy-prod.sh
   ```

## Environment-Specific Commands

### Development Commands

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Stop development environment
docker-compose -f docker-compose.dev.yml down

# View development logs
docker-compose -f docker-compose.dev.yml logs -f

# Rebuild development containers
docker-compose -f docker-compose.dev.yml up -d --build
```

### Production Commands

```bash
# Deploy to production
./scripts/deploy-prod.sh

# View production logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop production environment
docker-compose -f docker-compose.prod.yml down
```

## Important Notes

1. **Never commit environment files** - They contain sensitive information
2. **Always test in development** before deploying to production
3. **Use feature branches** for new development
4. **Keep development and production branches in sync** when appropriate

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 5173 and 8000 are available for development
2. **Database connection issues**: Check that the database container is running
3. **Environment variables**: Ensure all required environment variables are set

### Useful Commands

```bash
# Check running containers
docker ps

# Check container logs
docker logs <container_name>

# Reset development environment
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d --build
``` 