"""
Database configuration and session management for YudaiV3
"""
import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from unified models
from models import Base

# Database URL from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
)

# Create engine optimized for real-time features and SSE
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,  # Increased for concurrent SSE connections
    max_overflow=30,  # Allow burst connections for real-time updates
    pool_recycle=3600,  # Recycle connections every hour
    pool_timeout=30,  # Connection timeout
    echo=bool(os.getenv("DB_ECHO", "false").lower() == "true"),
    # Additional SSE-friendly settings
    connect_args={
        "application_name": "yudai_v3_sse",
        "options": "-c timezone=UTC"
    }
)
#TODO: Add pgvector (very important vector db)

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
        # Import all models here to ensure they are registered
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
        User, AuthToken, Repository, FileItem, ContextCard, IdeaItem,
        Issue, PullRequest, Commit, FileAnalysis, ChatSession, ChatMessage, UserIssue, FileEmbedding
    )
    
    db = SessionLocal()
    try:
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
                expires_at=datetime.utcnow() + timedelta(days=30),
                is_active=True
            ),
            AuthToken(
                user_id=2,
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                refresh_token=f"ghr_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=datetime.utcnow() + timedelta(days=30),
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
                github_created_at=datetime.utcnow() - timedelta(days=100),
                github_updated_at=datetime.utcnow() - timedelta(days=5),
                pushed_at=datetime.utcnow() - timedelta(days=1)
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
                github_created_at=datetime.utcnow() - timedelta(days=50),
                github_updated_at=datetime.utcnow() - timedelta(days=2),
                pushed_at=datetime.utcnow() - timedelta(hours=6)
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
                github_created_at=datetime.utcnow() - timedelta(days=10),
                github_updated_at=datetime.utcnow() - timedelta(days=2)
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
                github_created_at=datetime.utcnow() - timedelta(days=15),
                github_updated_at=datetime.utcnow() - timedelta(days=1),
                github_closed_at=datetime.utcnow() - timedelta(days=1)
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
                github_created_at=datetime.utcnow() - timedelta(days=5),
                github_updated_at=datetime.utcnow() - timedelta(days=1)
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
                author_date=datetime.utcnow() - timedelta(days=100)
            ),
            Commit(
                sha="def456abc789123",
                repository_id=1,
                message="Add user authentication feature",
                html_url="https://github.com/alice_dev/awesome-project/commit/def456abc789123",
                author_name="Alice Developer",
                author_email="alice@example.com",
                author_date=datetime.utcnow() - timedelta(days=5)
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
                processed_at=datetime.utcnow() - timedelta(days=1)
            )
        ]
        
        for analysis in sample_analyses:
            db.add(analysis)
        db.commit()
        
        # Sample ContextCards
        sample_context_cards = [
            ContextCard(
                user_id=1,
                title="Authentication System Design",
                description="Design patterns for implementing OAuth2 authentication",
                content="The authentication system should use OAuth2 with JWT tokens...",
                source="chat",
                tokens=800,
                is_active=True
            ),
            ContextCard(
                user_id=1,
                title="Database Schema",
                description="User and session management database schema",
                content="CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(255)...",
                source="file-deps",
                tokens=600,
                is_active=True
            )
        ]
        
        for card in sample_context_cards:
            db.add(card)
        db.commit()
        
        # Sample IdeaItems
        sample_ideas = [
            IdeaItem(
                user_id=1,
                title="Add real-time notifications",
                description="Implement WebSocket-based real-time notifications for user actions",
                complexity="M",
                status="pending",
                is_active=True
            ),
            IdeaItem(
                user_id=1,
                title="Implement caching layer",
                description="Add Redis caching to improve application performance",
                complexity="L",
                status="pending",
                is_active=True
            )
        ]
        
        for idea in sample_ideas:
            db.add(idea)
        db.commit()
        
        # Sample ChatSessions with repository context
        sample_sessions = [
            ChatSession(
                user_id=1,
                session_id="session_001",
                title="Authentication Discussion",
                description="Discussion about implementing OAuth2 authentication",
                repo_owner="alice_dev",
                repo_name="awesome-project",
                repo_branch="main",
                repo_context={
                    "owner": "alice_dev",
                    "name": "awesome-project",
                    "branch": "main",
                    "full_name": "alice_dev/awesome-project",
                    "html_url": "https://github.com/alice_dev/awesome-project",
                    "created_at": datetime.utcnow().isoformat()
                },
                is_active=True,
                total_messages=5,
                total_tokens=1200,
                last_activity=datetime.utcnow() - timedelta(hours=2)
            ),
            ChatSession(
                user_id=2,
                session_id="session_002",
                title="Database Design",
                description="Planning the database schema for the new feature",
                repo_owner="bob_coder",
                repo_name="cool-app",
                repo_branch="development",
                repo_context={
                    "owner": "bob_coder",
                    "name": "cool-app",
                    "branch": "development",
                    "full_name": "bob_coder/cool-app",
                    "html_url": "https://github.com/bob_coder/cool-app",
                    "created_at": datetime.utcnow().isoformat()
                },
                is_active=True,
                total_messages=3,
                total_tokens=800,
                last_activity=datetime.utcnow() - timedelta(hours=1)
            )
        ]
        
        for session in sample_sessions:
            db.add(session)
        db.commit()
        
        # Sample ChatMessages
        sample_messages = [
            ChatMessage(
                session_id=1,
                message_id="msg_001",
                message_text="How should we implement OAuth2 authentication?",
                sender_type="user",
                role="user",
                is_code=False,
                tokens=15,
                model_used="gpt-4",
                processing_time=1.2
            ),
            ChatMessage(
                session_id=1,
                message_id="msg_002",
                message_text="I recommend using the OAuth2 authorization code flow with PKCE for security...",
                sender_type="assistant",
                role="assistant",
                is_code=False,
                tokens=45,
                model_used="gpt-4",
                processing_time=2.1
            )
        ]
        
        for message in sample_messages:
            db.add(message)
        db.commit()
        
        # Sample UserIssues
        sample_user_issues = [
            UserIssue(
                user_id=1,
                issue_id="issue_001",
                context_card_id=1,
                issue_text_raw="Need help implementing OAuth2 authentication",
                issue_steps='["Set up OAuth2 provider", "Implement callback handler", "Add JWT token validation"]',
                title="OAuth2 Authentication Implementation",
                description="Help needed to implement OAuth2 authentication flow",
                conversation_id="conv_001",
                chat_session_id=1,
                context_cards='["card_001", "card_002"]',
                ideas='["idea_001"]',
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
        
        # Sample FileEmbeddings for session context
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
                file_metadata={
                    "size": 500,
                    "encoding": "utf-8",
                    "lines": 6
                }
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
                file_metadata={
                    "size": 200,
                    "encoding": "utf-8",
                    "lines": 3
                }
            )
        ]
        
        for file_embedding in sample_file_embeddings:
            db.add(file_embedding)
        db.commit()
        
        print("✓ Sample data created successfully")
        
    except Exception as e:
        print(f"✗ Error creating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close() 