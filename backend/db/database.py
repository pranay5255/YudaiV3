"""
Database configuration and session management for YudaiV3
"""
import os
import uuid
from datetime import timedelta

# Import Base from unified models
from models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils import utc_now

# Database URL from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
)

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
        Commit,
        FileAnalysis,
        FileItem,
        Issue,
        PullRequest,
        Repository,
        User,
        UserIssue,
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
        
        # Sample FileEmbeddings for session context (DISABLED - ChatSession model commented out)
        # sample_file_embeddings = [
        #     FileEmbedding(
        #         # session_id=1,  # DISABLED - ChatSession model commented out
        #         repository_id=1,
        #         file_path="src/main.py",
        #         file_name="main.py",
        #         file_type="python",
        #         file_content="# Main application file\n\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()",
        #         chunk_index=0,
        #         chunk_text="# Main application file\n\ndef main():\n    print('Hello, World!')",
        #         tokens=25,
        #         file_metadata={
        #             "size": 500,
        #             "encoding": "utf-8",
        #             "lines": 6
        #         }
        #     ),
        #     FileEmbedding(
        #         # session_id=1,  # DISABLED - ChatSession model commented out
        #         repository_id=1,
        #         file_path="requirements.txt",
        #         file_name="requirements.txt",
        #         file_type="text",
        #         file_content="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0",
        #         chunk_index=0,
        #         chunk_text="flask==2.0.1\nsqlalchemy==1.4.23\nrequests==2.26.0",
        #         tokens=15,
        #         file_metadata={
        #             "size": 200,
        #             "encoding": "utf-8",
        #             "lines": 3
        #         }
        #     )
        # ]
        # 
        # for file_embedding in sample_file_embeddings:
        #     db.add(file_embedding)
        # db.commit()
        
        print("✓ Sample data created successfully")
        
    except Exception as e:
        print(f"✗ Error creating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close() 