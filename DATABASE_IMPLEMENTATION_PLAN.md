# PostgreSQL Database Implementation Plan for YudaiV3

## Overview

This document outlines the implementation plan for integrating PostgreSQL database with the YudaiV3 application. The database will store user authentication tokens for GitHub and repository data extracted from the filedeps.py API.

## ✅ Completed Implementation

### 1. Database Schema & Models

**Created Files:**
- `backend/db/database.py` - SQLAlchemy configuration and session management
- `backend/db/models.py` - Database models for all tables
- `backend/db/__init__.py` - Package initialization
- `backend/db/init_db.py` - Database initialization script

**Database Tables:**
- `users` - User authentication and profile information
- `auth_tokens` - GitHub OAuth tokens and metadata
- `repositories` - Repository metadata and processing results
- `file_items` - Individual files from repository analysis (hierarchical structure)
- `context_cards` - User-created context cards
- `idea_items` - Ideas and feature requests

### 2. Docker Infrastructure

**Created Files:**
- `backend/db/Dockerfile` - PostgreSQL container configuration
- `backend/db/init.sql` - Database initialization SQL script
- `backend/Dockerfile` - Backend API container
- `Dockerfile` - Frontend React container  
- `nginx.conf` - Nginx configuration for frontend
- `docker-compose.yml` - Production orchestration
- `docker-compose.dev.yml` - Development orchestration
- `Makefile` - Docker management commands
- `DOCKER.md` - Comprehensive Docker documentation

**Updated Files:**
- `requirements.txt` - Added SQLAlchemy, psycopg2-binary, alembic

### 3. Container Architecture

The application now runs as three Docker containers:

1. **Frontend Container** (React + Nginx)
   - Port: 80 (production) / 5173 (development)
   - Serves static files and proxies API requests

2. **Backend Container** (FastAPI + Python)
   - Port: 8000
   - Handles API requests and database operations

3. **Database Container** (PostgreSQL)
   - Port: 5432
   - Stores all application data

## 🚧 Next Steps for Full Implementation

### Phase 1: Database Integration (Immediate)

1. **Update Backend Server**
   - Modify `backend/repo_processor/filedeps.py` to use database
   - Add database dependency injection to API endpoints
   - Implement repository data persistence


2. **Update API Models**
   - Modify existing Pydantic models to work with database
   - Add database response models


### Phase 2: Authentication System (Short-term)

1. **GitHub OAuth Integration**
   - Implement OAuth2 flow for GitHub
   - Create authentication endpoints
   - Add JWT token management

2. **User Management**
   - User registration and profile management
   - Token refresh and validation
   - Session management

3. **Security**
   - Add authentication middleware
   - Implement role-based access control
   - Secure API endpoints

### Phase 3: Data Persistence (Medium-term)

1. **Repository Processing**
   - Store extracted repository data
   - Cache processing results
   - Implement incremental updates

2. **User Data Management**
   - Context cards CRUD operations
   - Ideas management
   - User preferences

3. **Performance Optimization**
   - Add database indexes
   - Implement query optimization
   - Add caching layer

## 📋 Implementation Checklist

### Database Setup
- [x] PostgreSQL container configuration
- [x] SQLAlchemy models and relationships
- [x] Database initialization script
- [x] Docker orchestration
- [ ] Database migrations with Alembic
- [ ] Database seeders for development

### Backend Integration
- [ ] Update filedeps.py to use database
- [ ] Add database dependencies to FastAPI
- [ ] Implement repository data storage
- [ ] Add user authentication endpoints
- [ ] Create database service layer

### Frontend Integration
- [ ] Update API client to handle authentication
- [ ] Add login/logout functionality
- [ ] Implement user session management
- [ ] Add error handling for database operations

### DevOps & Production
- [x] Docker containerization
- [x] Development environment setup
- [x] Production deployment configuration
- [ ] Environment variable management
- [ ] Health checks and monitoring
- [ ] Backup and recovery procedures

## 🚀 Quick Start Guide

### Development Setup

```bash
# Clone repository and navigate to project
cd YudaiV3

# Start development environment
make dev-quickstart

# Or manually:
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --init
```

### Production Setup

```bash
# Start production environment
make quickstart

# Or manually:
docker-compose build
docker-compose up -d
docker-compose exec backend python db/init_db.py --init
```

### Database Management

```bash
# Check database health
make check-db

# Access database shell
make shell-db

# View database logs
make logs-db

# Backup database
make backup-db
```

## 📊 Database Schema Overview

### Core Tables

**users**
- Authentication and profile information
- GitHub integration metadata
- Timestamps for tracking

**auth_tokens**
- OAuth tokens for GitHub API
- Token metadata and expiration
- Linked to users table

**repositories**
- Repository metadata and processing status
- Raw and processed data storage (JSON)
- Processing statistics

**file_items**
- Hierarchical file structure
- File metadata and categorization
- Self-referencing for tree structure

### Supporting Tables

**context_cards**
- User-created context information
- Source tracking (chat, file-deps, upload)
- Content and metadata

**idea_items**
- Feature requests and ideas
- Complexity tracking
- Status management

## 🔧 Technical Details

### Database Connection
- Connection pooling with SQLAlchemy
- Environment-based configuration
- Health check endpoints

### Data Models
- Pydantic models for API validation
- SQLAlchemy models for database operations
- Automatic timestamp management

### Security
- Password hashing (to be implemented)
- OAuth token encryption
- Input validation and sanitization

## 📝 Environment Variables

Required environment variables for database operation:

```env
DATABASE_URL=postgresql://yudai_user:yudai_password@db:5432/yudai_db
POSTGRES_DB=yudai_db
POSTGRES_USER=yudai_user
POSTGRES_PASSWORD=yudai_password
DB_ECHO=false
```

## 🎯 Success Criteria

The database implementation will be considered complete when:

1. ✅ All three containers run successfully
2. ✅ Database tables are created automatically
3. ✅ Health checks pass for all services
4. ⏳ Repository data is stored and retrieved from database
5. ⏳ User authentication works with GitHub OAuth
6. ⏳ Frontend can interact with database-backed API
7. ⏳ Development and production environments are stable

## 🆘 Troubleshooting

### Common Issues

1. **Container startup failures**
   - Check Docker logs: `make logs`
   - Verify port availability
   - Check environment variables

2. **Database connection errors**
   - Verify database container is running
   - Check database initialization
   - Validate connection string

3. **API endpoint errors**
   - Check backend logs: `make logs-backend`
   - Verify database models are loaded
   - Check API documentation at `/docs`

### Development Tips

1. Use `make dev-up` for development with hot-reloading
2. Check container health with `make health`
3. Use `make shell-backend` to debug backend issues
4. Monitor logs with `make logs` during development

## 📚 Documentation

- **Docker Setup**: `DOCKER.md`
- **API Documentation**: Available at `http://localhost:8000/docs`
- **Database Schema**: See `backend/db/models.py`
- **Quick Commands**: Run `make help`

---

This implementation provides a solid foundation for the YudaiV3 application with proper database integration, containerization, and development workflow. 