"""
Database configuration and session management for YudaiV3
"""
import os
import uuid
from datetime import timedelta

# Import Base from unified models
from models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from utils import utc_now

# Database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Create engine with standard configuration
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    pool_timeout=30,
    echo=bool(os.getenv("DB_ECHO", "false").lower() == "true")
)
# Enable pgvector extension for vector similarity search
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable pgvector extension when connecting to PostgreSQL"""
    if DATABASE_URL.startswith("postgresql"):
        cursor = dbapi_connection.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.close()

# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency function to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database - create all tables using SQLAlchemy models
    """
    try:
        print("Initializing database with SQLAlchemy models...")
        
        # Create pgvector extension for PostgreSQL
        if DATABASE_URL.startswith("postgresql"):
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    print("✓ pgvector extension enabled")
            except Exception as e:
                print(f"⚠ Warning: Could not enable pgvector extension: {e}")
        
        # Import all models here to ensure they are registered with SQLAlchemy
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized successfully with SQLAlchemy models")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize database with SQLAlchemy models: {e}")
        print("Falling back to standalone SQL initialization...")
        return False

def create_sample_data():
    """
    Create sample data for all tables
    """
    from models import (
        AuthToken,
        ChatMessage,
        ChatSession,
        Commit,
        ContextCard,
        FileAnalysis,
        FileEmbedding,
        FileItem,
        Issue,
        PullRequest,
        Repository,
        User,
        UserIssue,
        # AI Solver models
        AIModel,
        SWEAgentConfig,
        AISolveSession,
        AISolveEdit,
    )
    
    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_users = db.query(User).filter(
            User.github_username.in_(["alice_dev", "bob_coder", "charlie_architect", "demo_user"])
        ).all()
        
        if existing_users:
            print("✓ Sample data already exists, skipping creation")
            print(f"Found {len(existing_users)} existing users: {[u.github_username for u in existing_users]}")
            return True
        
        print("📊 Creating sample data...")
        
        # Sample data for Users
        sample_users = [
            User(
                github_username="alice_dev",
                github_user_id="12345",
                email="alice@example.com",
                display_name="Alice Developer",
                avatar_url="https://avatars.githubusercontent.com/u/12345?v=4"
            ),
            User(
                github_username="bob_coder",
                github_user_id="67890",
                email="bob@example.com",
                display_name="Bob Coder",
                avatar_url="https://avatars.githubusercontent.com/u/67890?v=4"
            ),
            User(
                github_username="charlie_architect",
                github_user_id="11111",
                email="charlie@example.com",
                display_name="Charlie Architect",
                avatar_url="https://avatars.githubusercontent.com/u/11111?v=4"
            ),
            User(
                github_username="demo_user",
                github_user_id="19365600",
                email="demo@yudai.app",
                display_name="Demo User",
                avatar_url="https://avatars.githubusercontent.com/u/19365600?v=4"
            )
        ]
        
        for user in sample_users:
            db.add(user)
        db.commit()
        
        # Sample AuthTokens
        sample_tokens = [
            AuthToken(
                user_id=1,
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                refresh_token=f"ghr_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True
            ),
            AuthToken(
                user_id=2,
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                refresh_token=f"ghr_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True
            ),
            AuthToken(
                user_id=4,  # demo_user
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                refresh_token=f"ghr_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True
            )
        ]
        
        for token in sample_tokens:
            db.add(token)
        db.commit()
        
        # Sample Repositories
        sample_repos = [
            Repository(
                github_repo_id=123456789,
                user_id=1,
                name="awesome-project",
                owner="alice_dev",
                full_name="alice_dev/awesome-project",
                repo_url="https://github.com/alice_dev/awesome-project",
                description="An awesome project for demonstrating features",
                private=False,
                html_url="https://github.com/alice_dev/awesome-project",
                clone_url="https://github.com/alice_dev/awesome-project.git",
                language="Python",
                stargazers_count=42,
                forks_count=5,
                open_issues_count=3,
                github_created_at=utc_now() - timedelta(days=100),
                github_updated_at=utc_now() - timedelta(days=5),
                pushed_at=utc_now() - timedelta(days=1)
            ),
            Repository(
                github_repo_id=987654321,
                user_id=2,
                name="cool-app",
                owner="bob_coder",
                full_name="bob_coder/cool-app",
                repo_url="https://github.com/bob_coder/cool-app",
                description="A cool application with modern features",
                private=False,
                html_url="https://github.com/bob_coder/cool-app",
                clone_url="https://github.com/bob_coder/cool-app.git",
                language="TypeScript",
                stargazers_count=15,
                forks_count=2,
                open_issues_count=1,
                github_created_at=utc_now() - timedelta(days=50),
                github_updated_at=utc_now() - timedelta(days=2),
                pushed_at=utc_now() - timedelta(hours=6)
            )
        ]
        
        for repo in sample_repos:
            db.add(repo)
        db.commit()
        
        # Sample Issues
        sample_issues = [
            Issue(
                github_issue_id=1001,
                repository_id=1,
                number=1,
                title="Add user authentication feature",
                body="We need to implement user authentication with OAuth2",
                state="open",
                html_url="https://github.com/alice_dev/awesome-project/issues/1",
                author_username="alice_dev",
                github_created_at=utc_now() - timedelta(days=10),
                github_updated_at=utc_now() - timedelta(days=2)
            ),
            Issue(
                github_issue_id=1002,
                repository_id=1,
                number=2,
                title="Fix database connection issue",
                body="Database connection is failing in production",
                state="closed",
                html_url="https://github.com/alice_dev/awesome-project/issues/2",
                author_username="bob_coder",
                github_created_at=utc_now() - timedelta(days=15),
                github_updated_at=utc_now() - timedelta(days=1),
                github_closed_at=utc_now() - timedelta(days=1)
            )
        ]
        
        for issue in sample_issues:
            db.add(issue)
        db.commit()
        
        # Sample Pull Requests
        sample_prs = [
            PullRequest(
                github_pr_id=2001,
                repository_id=1,
                number=1,
                title="Implement user authentication",
                body="This PR adds OAuth2 authentication to the application",
                state="open",
                html_url="https://github.com/alice_dev/awesome-project/pull/1",
                author_username="alice_dev",
                github_created_at=utc_now() - timedelta(days=5),
                github_updated_at=utc_now() - timedelta(days=1)
            )
        ]
        
        for pr in sample_prs:
            db.add(pr)
        db.commit()
        
        # Sample Commits
        sample_commits = [
            Commit(
                sha="abc123def456789",
                repository_id=1,
                message="Initial commit: Add project structure",
                html_url="https://github.com/alice_dev/awesome-project/commit/abc123def456789",
                author_name="Alice Developer",
                author_email="alice@example.com",
                author_date=utc_now() - timedelta(days=100)
            ),
            Commit(
                sha="def456abc789123",
                repository_id=1,
                message="Add user authentication feature",
                html_url="https://github.com/alice_dev/awesome-project/commit/def456abc789123",
                author_name="Alice Developer",
                author_email="alice@example.com",
                author_date=utc_now() - timedelta(days=5)
            )
        ]
        
        for commit in sample_commits:
            db.add(commit)
        db.commit()
        
        # Sample FileItems
        sample_files = [
            FileItem(
                repository_id=1,
                name="main.py",
                path="src/main.py",
                file_type="INTERNAL",
                category="Source Code",
                tokens=1500,
                is_directory=False,
                content_size=5000,
                content="# Main application file\n\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()"
            ),
            FileItem(
                repository_id=1,
                name="requirements.txt",
                path="requirements.txt",
                file_type="INTERNAL",
                category="Dependencies",
                tokens=200,
                is_directory=False,
                content_size=500,
                content="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0"
            ),
            FileItem(
                repository_id=1,
                name="src",
                path="src",
                file_type="INTERNAL",
                category="Directory",
                tokens=0,
                is_directory=True,
                content_size=0
            )
        ]
        
        for file_item in sample_files:
            db.add(file_item)
        db.commit()
        
        # Sample FileAnalysis
        sample_analyses = [
            FileAnalysis(
                repository_id=1,
                raw_data='{"total_files": 15, "languages": {"Python": 10, "JavaScript": 5}}',
                processed_data='{"analysis": "complete", "complexity": "medium"}',
                total_files=15,
                total_tokens=25000,
                max_file_size=10000,
                status="completed",
                processed_at=utc_now() - timedelta(days=1)
            )
        ]
        
        for analysis in sample_analyses:
            db.add(analysis)
        db.commit()
        
        # Sample UserIssues
        sample_user_issues = [
            UserIssue(
                user_id=1,
                issue_id="issue_001",
                # context_card_id=1,
                issue_text_raw="Need help implementing OAuth2 authentication",
                issue_steps='["Set up OAuth2 provider", "Implement callback handler", "Add JWT token validation"]',
                title="OAuth2 Authentication Implementation",
                description="Help needed to implement OAuth2 authentication flow",
                session_id="session_001",
                # chat_session_id=1,  # DISABLED - ChatSession model commented out
                # context_cards='["card_001", "card_002"]',
                # ideas='["idea_001"]',
                repo_owner="alice_dev",
                repo_name="awesome-project",
                priority="high",
                status="pending",
                tokens_used=0
            )
        ]
        
        for user_issue in sample_user_issues:
            db.add(user_issue)
        db.commit()
        
        # Sample Chat Sessions
        sample_sessions = [
            ChatSession(
                user_id=1,
                session_id="session_001",
                title="Awesome Project Development",
                description="Working on OAuth2 authentication feature",
                repo_owner="alice_dev",
                repo_name="awesome-project",
                repo_branch="main",
                repo_context='{"language": "Python", "framework": "Flask"}',
                is_active=True,
                total_messages=0,
                total_tokens=0,
                last_activity=utc_now() - timedelta(hours=2)
            ),
            ChatSession(
                user_id=2,
                session_id="session_002",
                title="Cool App Enhancement",
                description="Adding new features to TypeScript application",
                repo_owner="bob_coder",
                repo_name="cool-app",
                repo_branch="main",
                repo_context='{"language": "TypeScript", "framework": "React"}',
                is_active=True,
                total_messages=0,
                total_tokens=0,
                last_activity=utc_now() - timedelta(minutes=30)
            )
        ]
        
        for session in sample_sessions:
            db.add(session)
        db.commit()
        
        # Sample Chat Messages
        sample_messages = [
            ChatMessage(
                session_id=1,
                message_id="msg_001",
                message_text="Hello! I need help implementing OAuth2 authentication for my Flask application.",
                sender_type="user",
                role="user",
                is_code=False,
                tokens=20
            ),
            ChatMessage(
                session_id=1,
                message_id="msg_002",
                message_text="I'd be happy to help you implement OAuth2 authentication! Let's start by setting up the OAuth2 provider configuration. What provider are you planning to use?",
                sender_type="assistant",
                role="assistant",
                is_code=False,
                tokens=35,
                model_used="gpt-4",
                processing_time=1200.5
            ),
            ChatMessage(
                session_id=2,
                message_id="msg_003",
                message_text="Can you help me optimize my React components for better performance?",
                sender_type="user",
                role="user",
                is_code=False,
                tokens=15
            )
        ]
        
        for message in sample_messages:
            db.add(message)
        db.commit()
        
        # Update session statistics
        db.execute(text("UPDATE chat_sessions SET total_messages = 2, total_tokens = 55 WHERE id = 1"))
        db.execute(text("UPDATE chat_sessions SET total_messages = 1, total_tokens = 15 WHERE id = 2"))
        db.commit()
        
        # Sample Context Cards
        sample_context_cards = [
            ContextCard(
                user_id=1,
                session_id=1,
                title="OAuth2 Flow Documentation",
                description="Essential OAuth2 implementation guide",
                content="OAuth2 is an authorization framework that enables applications to obtain limited access to user accounts...",
                source="upload",
                tokens=150
            ),
            ContextCard(
                user_id=1,
                session_id=1,
                title="Flask-OAuthlib Example",
                description="Code example for Flask OAuth integration",
                content="```python\nfrom flask_oauthlib.client import OAuth\n\noauth = OAuth(app)\n```",
                source="chat",
                tokens=75,
                is_active=True
            ),
            ContextCard(
                user_id=2,
                session_id=2,
                title="React Performance Tips",
                description="Best practices for React optimization",
                content="1. Use React.memo for functional components\n2. Implement useMemo for expensive calculations\n3. Use useCallback for function references",
                source="chat",
                tokens=120
            )
        ]
        
        for context_card in sample_context_cards:
            db.add(context_card)
        db.commit()
        
        # Sample File Embeddings for session context
        sample_file_embeddings = [
            FileEmbedding(
                session_id=1,
                repository_id=1,
                file_path="src/main.py",
                file_name="main.py",
                file_type="python",
                file_content="# Main application file\n\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()",
                chunk_index=0,
                chunk_text="# Main application file\n\ndef main():\n    print('Hello, World!')",
                tokens=25,
                file_metadata='{"size": 500, "encoding": "utf-8", "lines": 6}'
            ),
            FileEmbedding(
                session_id=1,
                repository_id=1,
                file_path="requirements.txt",
                file_name="requirements.txt",
                file_type="text",
                file_content="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0",
                chunk_index=0,
                chunk_text="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0",
                tokens=15,
                file_metadata='{"size": 200, "encoding": "utf-8", "lines": 3}'
            )
        ]
        
        for file_embedding in sample_file_embeddings:
            db.add(file_embedding)
        db.commit()
        
        # Sample AI Models
        sample_ai_models = [
            AIModel(
                name="Claude 3.5 Sonnet",
                provider="openrouter",
                model_id="anthropic/claude-3.5-sonnet",
                config={
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "top_p": 0.9
                },
                is_active=True
            ),
            AIModel(
                name="GPT-4 Turbo",
                provider="openrouter",
                model_id="openai/gpt-4-turbo",
                config={
                    "temperature": 0.2,
                    "max_tokens": 4000,
                    "top_p": 0.95
                },
                is_active=True
            ),
            AIModel(
                name="DeepSeek Coder",
                provider="openrouter",
                model_id="deepseek/deepseek-coder",
                config={
                    "temperature": 0.1,
                    "max_tokens": 8000,
                    "top_p": 0.9
                },
                is_active=False
            )
        ]
        
        for ai_model in sample_ai_models:
            db.add(ai_model)
        db.commit()
        
        # Sample SWE-agent Configurations
        sample_swe_configs = [
            SWEAgentConfig(
                name="Default Config",
                config_path="/app/solver/config.yaml",
                parameters={
                    "max_iterations": 50,
                    "max_time_seconds": 1800,
                    "max_cost": 10.0,
                    "environment": {
                        "image": "sweagent/swe-agent:latest",
                        "data_path": "/data/swe_runs"
                    }
                },
                is_default=True
            ),
            SWEAgentConfig(
                name="Fast Config",
                config_path="/app/solver/config-fast.yaml",
                parameters={
                    "max_iterations": 25,
                    "max_time_seconds": 900,
                    "max_cost": 5.0,
                    "environment": {
                        "image": "sweagent/swe-agent:latest",
                        "data_path": "/data/swe_runs"
                    }
                },
                is_default=False
            ),
            SWEAgentConfig(
                name="Extended Config",
                config_path="/app/solver/config-extended.yaml",
                parameters={
                    "max_iterations": 100,
                    "max_time_seconds": 3600,
                    "max_cost": 20.0,
                    "environment": {
                        "image": "sweagent/swe-agent:latest",
                        "data_path": "/data/swe_runs"
                    }
                },
                is_default=False
            )
        ]
        
        for swe_config in sample_swe_configs:
            db.add(swe_config)
        db.commit()
        
        # Sample AI Solve Sessions
        sample_solve_sessions = [
            AISolveSession(
                user_id=1,
                issue_id=1,  # "Add user authentication feature"
                ai_model_id=1,  # Claude 3.5 Sonnet
                swe_config_id=1,  # Default Config
                status="completed",
                repo_url="https://github.com/alice_dev/awesome-project.git",
                branch_name="main",
                trajectory_data={
                    "steps": [
                        {"step_index": 1, "action": "explore_repository", "timestamp": "2024-01-15T10:00:00Z"},
                        {"step_index": 2, "action": "analyze_issue", "timestamp": "2024-01-15T10:05:00Z"},
                        {"step_index": 3, "action": "create_auth_module", "timestamp": "2024-01-15T10:15:00Z"},
                        {"step_index": 4, "action": "implement_oauth", "timestamp": "2024-01-15T10:30:00Z"},
                        {"step_index": 5, "action": "add_tests", "timestamp": "2024-01-15T10:45:00Z"}
                    ],
                    "final_state": "completed",
                    "total_steps": 5
                },
                started_at=utc_now() - timedelta(days=5),
                completed_at=utc_now() - timedelta(days=5, hours=-1)
            ),
            AISolveSession(
                user_id=2,
                issue_id=2,  # "Fix database connection issue"
                ai_model_id=2,  # GPT-4 Turbo
                swe_config_id=2,  # Fast Config
                status="failed",
                repo_url="https://github.com/alice_dev/awesome-project.git",
                branch_name="main",
                trajectory_data={
                    "steps": [
                        {"step_index": 1, "action": "explore_repository", "timestamp": "2024-01-10T14:00:00Z"},
                        {"step_index": 2, "action": "analyze_database_config", "timestamp": "2024-01-10T14:10:00Z"}
                    ],
                    "final_state": "failed",
                    "total_steps": 2
                },
                error_message="Failed to connect to database during analysis phase",
                started_at=utc_now() - timedelta(days=10),
                completed_at=utc_now() - timedelta(days=10, hours=-1)
            ),
            AISolveSession(
                user_id=1,
                issue_id=1,  # Another attempt at the same issue
                ai_model_id=1,  # Claude 3.5 Sonnet
                swe_config_id=1,  # Default Config
                status="running",
                repo_url="https://github.com/alice_dev/awesome-project.git",
                branch_name="feature/auth-v2",
                trajectory_data={
                    "steps": [
                        {"step_index": 1, "action": "explore_repository", "timestamp": "2024-01-20T09:00:00Z"},
                        {"step_index": 2, "action": "create_branch", "timestamp": "2024-01-20T09:05:00Z"},
                        {"step_index": 3, "action": "analyze_requirements", "timestamp": "2024-01-20T09:10:00Z"}
                    ],
                    "final_state": "running",
                    "total_steps": 3
                },
                started_at=utc_now() - timedelta(hours=2)
            )
        ]
        
        for solve_session in sample_solve_sessions:
            db.add(solve_session)
        db.commit()
        
        # Sample AI Solve Edits
        sample_solve_edits = [
            AISolveEdit(
                session_id=1,  # First completed session
                file_path="src/auth/__init__.py",
                edit_type="create",
                original_content=None,
                new_content="# Authentication module\n\nfrom .oauth import OAuth2Handler\nfrom .middleware import AuthMiddleware\n\n__all__ = ['OAuth2Handler', 'AuthMiddleware']",
                metadata={
                    "step_index": 3,
                    "timestamp": "2024-01-15T10:15:00Z",
                    "command": "create_file"
                }
            ),
            AISolveEdit(
                session_id=1,
                file_path="src/auth/oauth.py",
                edit_type="create",
                original_content=None,
                new_content="import requests\nfrom flask import session, redirect, url_for\n\nclass OAuth2Handler:\n    def __init__(self, client_id, client_secret):\n        self.client_id = client_id\n        self.client_secret = client_secret\n    \n    def get_auth_url(self):\n        # OAuth2 implementation\n        pass",
                metadata={
                    "step_index": 4,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "command": "create_file"
                }
            ),
            AISolveEdit(
                session_id=1,
                file_path="requirements.txt",
                edit_type="modify",
                original_content="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0",
                new_content="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0\nflask-oauthlib==0.9.6\npyjwt==2.4.0",
                line_start=1,
                line_end=3,
                metadata={
                    "step_index": 4,
                    "timestamp": "2024-01-15T10:32:00Z",
                    "command": "str_replace_editor"
                }
            ),
            AISolveEdit(
                session_id=1,
                file_path="tests/test_auth.py",
                edit_type="create",
                original_content=None,
                new_content="import unittest\nfrom src.auth import OAuth2Handler\n\nclass TestOAuth2Handler(unittest.TestCase):\n    def setUp(self):\n        self.handler = OAuth2Handler('test_id', 'test_secret')\n    \n    def test_initialization(self):\n        self.assertEqual(self.handler.client_id, 'test_id')\n        self.assertEqual(self.handler.client_secret, 'test_secret')",
                metadata={
                    "step_index": 5,
                    "timestamp": "2024-01-15T10:45:00Z",
                    "command": "create_file"
                }
            )
        ]
        
        for solve_edit in sample_solve_edits:
            db.add(solve_edit)
        db.commit()
        
        print("✓ Sample data created successfully")
        
    except Exception as e:
        print(f"✗ Error creating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def reset_sample_data():
    """
    Reset sample data by removing existing sample users and recreating them
    """
    from models import User
    
    db = SessionLocal()
    try:
        print("🗑️  Resetting sample data...")
        
        # Delete sample data in reverse dependency order
        sample_usernames = ["alice_dev", "bob_coder", "charlie_architect", "demo_user"]
        
        # Find and delete sample users
        sample_users = db.query(User).filter(
            User.github_username.in_(sample_usernames)
        ).all()
        
        if sample_users:
            print(f"Found {len(sample_users)} sample users to delete")
            for user in sample_users:
                db.delete(user)
            db.commit()
            print("✓ Sample users deleted")
        else:
            print("No sample users found to delete")
        
        # Create fresh sample data
        return create_sample_data()
        
    except Exception as e:
        print(f"✗ Error resetting sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()