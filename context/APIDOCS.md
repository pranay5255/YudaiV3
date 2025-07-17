# YudaiV3 Backend API

A unified FastAPI server that combines all backend services for the YudaiV3 application.

## Services Included

### 🔐 Authentication (`/auth`)
- GitHub OAuth authentication
- User session management
- Profile management

### 🐙 GitHub Integration (`/github`)
- Repository management
- Issue creation and management
- Pull request handling
- Repository search

### 💬 Chat Services (`/daifu`)
- DAifu AI agent integration
- Chat session management
- Message history
- Issue creation from chat

### 📋 Issue Management (`/issues`)
- User issue creation and management
- Issue status tracking
- GitHub issue conversion
- Issue statistics

### 📁 File Dependencies (`/filedeps`)
- Repository file structure extraction
- File dependency analysis
- GitIngest integration
- File categorization

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database
- GitHub OAuth app configured

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your configuration
```

3. Initialize the database:
```bash
python init_db.py
```

4. Start the server:
```bash
python run_server.py
```

The server will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Root Endpoints
- `GET /` - API information and service overview
- `GET /health` - Health check

### Authentication
- `GET /auth/login` - GitHub OAuth login
- `GET /auth/callback` - OAuth callback
- `GET /auth/profile` - User profile
- `POST /auth/logout` - Logout
- `GET /auth/status` - Auth status
- `GET /auth/config` - Auth configuration

### GitHub Integration
- `GET /github/repositories` - User repositories
- `GET /github/repositories/{owner}/{repo}` - Repository details
- `POST /github/repositories/{owner}/{repo}/issues` - Create issue
- `GET /github/repositories/{owner}/{repo}/issues` - Repository issues
- `GET /github/repositories/{owner}/{repo}/pulls` - Repository PRs
- `GET /github/repositories/{owner}/{repo}/commits` - Repository commits
- `GET /github/search/repositories` - Search repositories

### Chat Services
- `POST /daifu/chat/daifu` - Chat with DAifu agent
- `GET /daifu/chat/sessions` - Chat sessions
- `GET /daifu/chat/sessions/{session_id}/messages` - Session messages
- `GET /daifu/chat/sessions/{session_id}/statistics` - Session statistics
- `PUT /daifu/chat/sessions/{session_id}/title` - Update session title
- `DELETE /daifu/chat/sessions/{session_id}` - Deactivate session
- `POST /daifu/chat/create-issue` - Create issue from chat

### Issue Management
- `POST /issues/` - Create user issue
- `GET /issues/` - Get user issues
- `GET /issues/{issue_id}` - Get specific issue
- `PUT /issues/{issue_id}/status` - Update issue status
- `POST /issues/{issue_id}/convert-to-github` - Convert to GitHub issue
- `POST /issues/from-chat` - Create issue from chat
- `GET /issues/statistics` - Issue statistics

### File Dependencies
- `GET /filedeps/` - File dependencies API info
- `GET /filedeps/repositories` - User repositories
- `GET /filedeps/repositories/{repository_id}` - Repository details
- `GET /filedeps/repositories/{repository_id}/files` - Repository files
- `POST /filedeps/extract` - Extract file dependencies

## Docker Deployment

### Using Docker Compose
```bash
docker-compose up -d
```

### Using Docker directly
```bash
docker build -t yudai-v3-backend .
docker run -p 8000:8000 yudai-v3-backend
```

## Environment Variables

Required environment variables (see `env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `GITHUB_CLIENT_ID` - GitHub OAuth app client ID
- `GITHUB_CLIENT_SECRET` - GitHub OAuth app client secret
- `GITHUB_REDIRECT_URI` - OAuth redirect URI
- `OPENROUTER_API_KEY` - OpenRouter API key for DAifu agent
- `SECRET_KEY` - Application secret key

## Development

## Error Handling

All endpoints include proper error handling with appropriate HTTP status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

## CORS Configuration

The server is configured to allow requests from:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)

