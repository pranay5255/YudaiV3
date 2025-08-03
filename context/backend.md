# YudaiV3 Backend Architecture

**Last Updated**: January 2025  
**Framework**: FastAPI 0.104+  
**Database**: PostgreSQL with SQLAlchemy ORM  
**Status**: 🟡 PARTIALLY READY - CRITICAL FIXES REQUIRED

## 🚨 CRITICAL NOTICE

The backend has **6 critical issues** that prevent demo deployment:
1. 🔒 WebSocket authentication vulnerabilities
2. 💾 Missing pgvector database extension  
3. 🐛 File dependencies service completely broken
4. ⚠️ Session ID inconsistency causing state corruption
5. 🔓 Exposed development secrets
6. 🌐 Insecure CORS configuration

---

## 🏗️ UNIFIED ARCHITECTURE OVERVIEW

### Core Framework Structure
```python
# backend/run_server.py - Unified FastAPI Application
app = FastAPI(
    title="YudaiV3 Backend API",
    description="Unified backend API for YudaiV3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan  # Database initialization
)
```

### Service-Oriented Design
```
YudaiV3 Backend (FastAPI)
├── 🔐 Authentication Service (/auth)
│   ├── GitHub OAuth2 flow
│   ├── JWT token management  
│   └── User profile handling
├── 🐙 GitHub Integration (/github)
│   ├── Repository management
│   ├── Issue operations
│   └── Pull request tracking
├── 💬 DaifuUserAgent (/daifu)
│   ├── AI chat conversations
│   ├── Session management
│   ├── WebSocket real-time updates ⚠️
│   └── Context card handling
├── 📋 Issue Management (/issues)
│   ├── User issue lifecycle
│   ├── GitHub issue integration
│   └── Chat-to-issue conversion
└── 📁 File Dependencies (/filedeps) ❌
    ├── Repository analysis (BROKEN)
    ├── File tree extraction (BROKEN)
    ├── Dependency mapping (BROKEN)
    └── Vector embeddings (MISSING)
```

---

## 🗄️ DATABASE ARCHITECTURE

### Current Database Schema

#### Core Tables (Working)
```sql
-- User Management
users (id, github_username, github_user_id, email, display_name, avatar_url)
auth_tokens (id, user_id, access_token, expires_at, is_active)

-- Repository Data  
repositories (id, github_repo_id, user_id, name, owner, full_name)
issues (id, github_issue_id, repository_id, number, title, state)
pull_requests (id, github_pr_id, repository_id, number, title, state)
commits (id, sha, repository_id, message)

-- Chat System
chat_sessions (id, user_id, session_id, title, created_at, updated_at)
chat_messages (id, session_id, message_text, sender_type, created_at)

-- Issue Management
user_issues (id, user_id, chat_session_id, title, description, status)
context_cards (id, user_id, title, content, source, created_at)
```

#### Broken/Missing Tables
```sql
-- ❌ BROKEN: File analysis system
file_items (id, repository_id, name, path, is_directory, parent_id)
file_analyses (id, repository_id, status, created_at)

-- ❌ MISSING: Vector embeddings (requires pgvector)
file_embeddings (id, session_id, file_path, embedding, user_id)
```

### Database Configuration Issues
```python
# backend/db/database.py
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
)

# ❌ CRITICAL MISSING: pgvector extension
#TODO: Add pgvector (very important vector db)

# ⚠️ SUBOPTIMAL: Connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_size=20,        # Too high for development
    max_overflow=30,     # Excessive
    pool_recycle=3600,   # Could be optimized
)
```

---

## 🔐 AUTHENTICATION SERVICE

### Implementation: `backend/auth/`
```
auth/
├── __init__.py
├── auth_routes.py      # FastAPI route handlers
├── auth_utils.py       # Utility functions
└── github_oauth.py     # OAuth2 implementation
```

### OAuth2 Flow Implementation
```python
# backend/auth/github_oauth.py
async def github_callback(code: str, state: str, db: Session) -> Dict:
    """
    ✅ WORKING: Complete GitHub OAuth2 implementation
    - Exchange code for access token
    - Fetch user profile from GitHub
    - Create/update user in database
    - Generate JWT token
    - Handle token expiration
    """
```

### JWT Token Management
```python
# backend/auth/auth_utils.py
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    ✅ WORKING: Secure JWT token creation
    - RS256 algorithm
    - Configurable expiration
    - User claims embedding
    """
```

### Current Auth Issues
- ✅ OAuth flow working correctly
- ✅ JWT implementation secure
- ⚠️ **Token validation in WebSockets vulnerable**
- ⚠️ **No rate limiting on auth endpoints**

---

## 🐙 GITHUB INTEGRATION SERVICE

### Implementation: `backend/github/`
```
github/
├── __init__.py
├── github_api.py       # GitHub API client
└── github_routes.py    # FastAPI route handlers
```

### GitHub API Client
```python
# backend/github/github_api.py
class GitHubAPIClient:
    """
    ✅ WORKING: Comprehensive GitHub API integration
    - Repository operations (list, get, search)
    - Issue management (list, create, update)
    - Pull request tracking
    - Commit history access
    - Branch listing
    """
    
    def __init__(self, access_token: str):
        self.token = access_token
        self.base_url = "https://api.github.com"
```

### Repository Management
```python
async def get_user_repositories(current_user: User, db: Session):
    """
    ✅ WORKING: Complete repository management
    - Fetch user repositories from GitHub
    - Cache repository metadata
    - Support pagination and filtering
    """
```

### Issue Integration
```python
async def create_repository_issue(
    owner: str, repo: str, issue_data: dict, current_user: User
):
    """
    ✅ WORKING: GitHub issue creation
    - Create issues directly in GitHub
    - Link to internal user issues
    - Preserve context and metadata
    """
```

---

## 💬 DAIFU CHAT SERVICE ⚠️ CRITICAL ISSUES

### Implementation: `backend/daifuUserAgent/`
```
daifuUserAgent/
├── __init__.py
├── chat_api.py             # Main chat endpoints ⚠️
├── llm_service.py          # LLM integration ✅
├── message_service.py      # Message handling ✅
├── websocket_manager.py    # Real-time management ❌
└── architectAgent/
    ├── code_inspector_service.py
    ├── promptTemplate.py
    └── example_usage.py
```

### AI Chat Implementation
```python
# backend/daifuUserAgent/chat_api.py
@router.post("/chat/daifu")
async def chat_daifu(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ⚠️ WORKING BUT ISSUES:
    - Basic chat functionality works
    - AI responses generated correctly
    - Context preservation implemented
    - BUT: Session ID naming inconsistency
    - BUT: No rate limiting
    """
```

### Session Management
```python
# backend/issueChatServices/session_service.py
class SessionService:
    """
    ⚠️ PARTIAL IMPLEMENTATION:
    ✅ Session creation and retrieval
    ✅ Context card management
    ✅ Repository binding
    ❌ Session ID consistency issues
    ❌ WebSocket session synchronization broken
    """
    
    @staticmethod
    def create_session(db: Session, user_id: int, repo_owner: str, repo_name: str):
        # ⚠️ ISSUE: Session ID format inconsistency
        session_id = f"{repo_owner}_{repo_name}_{repo_branch}_{timestamp}"
```

### 🔴 CRITICAL: WebSocket Implementation
```python
# backend/daifuUserAgent/chat_api.py
@router.websocket("/sessions/{session_id}/ws")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    🔴 CRITICAL SECURITY VULNERABILITY:
    1. Connection accepts BEFORE authentication
    2. User can access websocket without valid token
    3. No rate limiting on connections
    4. Race conditions in auth validation
    """
    
    # ❌ BROKEN: Connection established first
    await websocket.accept()
    
    # ❌ VULNERABLE: Auth happens after connection
    try:
        if not token:
            await websocket.send_text(json.dumps({"error": "No token provided"}))
            return
            
        # Auth validation happens HERE - too late!
        user = await get_current_user(token, db)
    except Exception as e:
        # User already connected!
        await websocket.send_text(json.dumps({"error": "Authentication failed"}))
```

### WebSocket Message Flow
```python
# Current message types (working)
MESSAGE_TYPES = {
    "SESSION_UPDATE": "session_update",      # ✅ Working
    "MESSAGE": "message",                    # ✅ Working  
    "CONTEXT_CARD": "context_card",          # ✅ Working
    "AGENT_STATUS": "agent_status",          # ✅ Working
    "STATISTICS": "statistics",              # ✅ Working
    "HEARTBEAT": "heartbeat",                # ✅ Working
    "ERROR": "error"                         # ✅ Working
}
```

---

## 📋 ISSUE MANAGEMENT SERVICE

### Implementation: `backend/issueChatServices/`
```
issueChatServices/
├── __init__.py
├── issue_service.py        # Issue CRUD operations ✅
├── chat_service.py         # Chat integration ✅
└── session_service.py      # Session management ⚠️
```

### Issue Lifecycle Management
```python
# backend/issueChatServices/issue_service.py
class IssueService:
    """
    ✅ WORKING: Complete issue management
    - Create user issues from chat
    - Link to GitHub repositories
    - Convert to GitHub issues
    - Track issue statistics
    - Preserve chat context
    """
    
    @staticmethod
    async def create_issue_with_context(
        issue_data: CreateUserIssueRequest,
        context_cards: List[str],
        chat_session_id: Optional[str],
        user_id: int,
        db: Session
    ):
        # ✅ WORKING: Context preservation
```

### GitHub Integration
```python
async def create_github_issue_from_user_issue(
    issue_id: int, 
    github_data: dict,
    current_user: User,
    db: Session
):
    """
    ✅ WORKING: Seamless GitHub integration
    - Convert internal issues to GitHub
    - Preserve all context and metadata
    - Link back to original conversation
    """
```

---

## 📁 FILE DEPENDENCIES SERVICE ❌ COMPLETELY BROKEN

### Implementation: `backend/repo_processorGitIngest/`
```
repo_processorGitIngest/
├── __init__.py
├── filedeps.py            # Main service ❌ BROKEN
├── README.md              # Documentation
└── file_processor.py      # File analysis ❌ MISSING
```

### 🔴 CRITICAL ISSUES

#### 1. Missing pgvector Extension
```python
# backend/db/database.py:34
#TODO: Add pgvector (very important vector db)

# ❌ CONSEQUENCE: All file embedding operations fail
# ❌ IMPACT: Core feature completely unusable
```

#### 2. Broken File Tree Implementation
```python
# backend/repo_processorGitIngest/filedeps.py
@router.get("/repositories/{repository_id}/files")
async def get_repository_files(repository_id: int):
    """
    ❌ BROKEN: File tree extraction fails
    - Database queries timeout
    - Memory leaks with large repositories
    - Infinite recursion in file hierarchy
    """
```

#### 3. Missing Vector Embeddings
```python
# File embeddings table exists but can't be used
file_embeddings = Table(
    "file_embeddings",
    # ❌ BROKEN: pgvector column type not available
    Column("embedding", pgvector.Vector(1536))  # FAILS
)
```

---

## 🔄 REAL-TIME COMMUNICATION

### WebSocket Manager Architecture
```python
# backend/daifuUserAgent/websocket_manager.py (conceptual)
class UnifiedWebSocketManager:
    """
    ⚠️ PARTIALLY IMPLEMENTED:
    - Connection management working
    - Message routing functional
    - Authentication vulnerable
    - No rate limiting
    - rate limiting implemented in frontend
    - Poor error handling
    """
    
    def __init__(self):
        self.active_connections = {}
        self.session_rooms = {}
        
    async def connect(self, websocket: WebSocket, session_id: str, user_id: int):
        # ⚠️ ISSUE: No authentication validation here
```

### Message Broadcasting
```python
async def broadcast_to_session(self, session_id: str, message: dict):
    """
    ✅ WORKING: Message broadcasting
    - Send updates to all session participants
    - Handle connection failures gracefully
    - Support multiple message types
    """
```

---

## 🚦 MIDDLEWARE & SECURITY

### CORS Configuration
```python
# backend/run_server.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173",  
        "https://yudai.app",      
        "http://yudai.app"        # ❌ SECURITY ISSUE: HTTP in production
    ],
    allow_credentials=True,
    allow_methods=["*"],         # ❌ TOO PERMISSIVE
    allow_headers=["*"],         # ❌ TOO PERMISSIVE
)
```

### Missing Security Middleware
```python
# ❌ MISSING: Rate limiting
# ❌ MISSING: Request size limits
# ❌ MISSING: Security headers
# ❌ MISSING: IP filtering
# ❌ MISSING: Request logging
```
#TODO: need to completely implement this using middleware.

---

## 🗂️ DATA FLOW ARCHITECTURE

### User Authentication Flow
```
1. User → GET /auth/login → Redirect to GitHub
2. GitHub → GET /auth/callback → Exchange code for token
3. Backend → Create/update user → Store auth token
4. Backend → Generate JWT → Return to frontend
5. Frontend → Store JWT → Use in Authorization header
```

### Chat Session Flow
```
1. User selects repository → POST /daifu/sessions
2. Backend creates session → Returns session_id
3. Frontend establishes WebSocket → WS /daifu/sessions/{id}/ws
4. User sends message → POST /daifu/chat/daifu
5. AI processes message → Background task
6. AI response → WebSocket broadcast to frontend
7. Frontend updates UI → Real-time experience
```

### Issue Creation Flow
```
1. User creates issue from chat → POST /issues/create-with-context
2. Backend preserves chat context → Links to session
3. User converts to GitHub issue → POST /issues/{id}/create-github-issue
4. Backend creates GitHub issue → Preserves links
5. User tracks issue lifecycle → GET /issues/{id}
```

---

## 🔧 DEPLOYMENT ARCHITECTURE

### Docker Container Structure
```
YudaiV3 Deployment
├── 🗄️ Database (PostgreSQL)
│   ├── Container: yudai-db[-staging]
│   ├── Port: 5432 (internal)
│   ├── Volume: postgres_data[_staging]
│   └── Issues: ❌ Missing pgvector extension
├── 🔧 Backend (FastAPI)
│   ├── Container: yudai-be[-staging]
│   ├── Port: 127.0.0.1:8000:8000 (prod) / 8001:8000 (staging)
│   ├── Issues: ❌ Exposed secrets, vulnerable WebSockets
│   └── Health: ✅ Basic health check working
└── 🌐 Frontend (React + Nginx)
    ├── Container: yudai-fe[-staging]
    ├── Ports: 80/443 (prod) / 8080/8443 (staging)
    ├── SSL: ⚠️ No certificate validation
    └── Issues: ❌ Missing health endpoints
```

### Environment Configuration Issues
```yaml
# docker-compose.dev.yml
#TODO: deleted this file
environment:
  - SECRET_KEY=${SECRET_KEY:-dev_secret}     # ❌ EXPOSED SECRET
  - JWT_SECRET=${JWT_SECRET:-dev_jwt_secret} # ❌ EXPOSED SECRET
  - NODE_ENV=staging                         # ❌ INCONSISTENT
```

---

## 🚨 CRITICAL FIXES REQUIRED FOR DEMO

### Phase 1: Security (Immediate)
1. **Fix WebSocket Authentication**
   ```python
   # Move auth BEFORE websocket.accept()
   @router.websocket("/sessions/{session_id}/ws")
   async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str):
       # ✅ FIX: Validate auth FIRST
       user = await validate_websocket_token(token, db)
       if not user:
           await websocket.close(code=4001, reason="Unauthorized")
           return
       
       # Only then accept connection
       await websocket.accept()
   ```

2. **Remove Exposed Secrets**
   ```yaml
   # ❌ REMOVE these fallbacks
   SECRET_KEY=${SECRET_KEY:-dev_secret}
   JWT_SECRET=${JWT_SECRET:-dev_jwt_secret}
   
   # ✅ ADD proper validation
   SECRET_KEY=${SECRET_KEY}  # Required, no fallback
   ```

3. **Fix CORS Configuration**
   ```python
   # ✅ Environment-specific CORS
   if os.getenv("NODE_ENV") == "production":
       allow_origins=["https://yudai.app"]
   else:
       allow_origins=["http://localhost:3000", "http://localhost:5173"]
   ```

### Phase 2: Core Functionality (Day 2)
1. **Implement pgvector Extension**
   ```sql
   -- Add to database initialization
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Fix File Dependencies Service**
   ```python
   # Rewrite file tree extraction
   # Fix infinite recursion bugs
   # Implement proper error handling
   ```

3. **Standardize Session Management**
   ```python
   # Use consistent session_id format
   # Fix WebSocket session synchronization
   # Implement proper state management
   ```

### Phase 3: Production Readiness (Day 3)
1. **Add Rate Limiting**
2. **Implement Proper Logging**
3. **Add Monitoring Endpoints**
4. **Complete Error Handling**

---

## 📊 BACKEND HEALTH METRICS

| Component | Status | Issues | Priority |
|-----------|--------|--------|----------|
| Auth Service | ✅ Stable | None | Low |
| GitHub Integration | ✅ Stable | None | Low |
| Chat Service | ⚠️ Partial | WebSocket security | HIGH |
| Issue Management | ✅ Stable | None | Low |
| File Dependencies | ❌ Broken | Complete rewrite needed | CRITICAL |
| Database | ⚠️ Partial | Missing pgvector | CRITICAL |
| Security | ❌ Vulnerable | Multiple issues | CRITICAL |
| Deployment | ⚠️ Partial | Configuration issues | HIGH |

---

## 🎯 SUCCESS CRITERIA FOR DEMO READINESS

- [ ] All WebSocket connections secure and authenticated
- [ ] File dependencies service fully functional
- [ ] No exposed secrets or debug code
- [ ] Proper error handling and logging
- [ ] Fast response times (< 2s for API calls)
- [ ] Stable database with all required extensions
- [ ] Production-ready configuration
- [ ] Comprehensive health checks

---

**Status**: The backend requires immediate fixes to critical security and functionality issues before demo deployment. Focus on Phase 1 security fixes first, then address core functionality gaps.