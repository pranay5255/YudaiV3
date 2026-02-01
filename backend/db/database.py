"""
Database configuration and session management for YudaiV3
"""

import os
import uuid
from datetime import timedelta
from contextlib import contextmanager

import requests
import psycopg
from psycopg.rows import dict_row

from sqlalchemy import create_engine, event, text
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
    echo=bool(os.getenv("DB_ECHO", "false").lower() == "true"),
)


# Enable pgvector extension for vector similarity search
@event.listens_for(engine, "connect")
def set_postgres_pragma(dbapi_connection, connection_record):
    """Enable pgvector extension when connecting to PostgreSQL"""
    if DATABASE_URL.startswith("postgresql"):
        cursor = dbapi_connection.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cursor.close()


# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency function to get database session (ORM - kept for backward compatibility during migration)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_raw_connection():
    """Get raw psycopg3 connection using same connection string as SQLAlchemy"""
    conn = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row  # Return rows as dicts
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_connection():
    """FastAPI dependency for database connection (vanilla SQL)"""
    with get_raw_connection() as conn:
        yield conn


def init_db():
    """
    Initialize database - create all tables using SQL schema file
    """
    try:
        print("Initializing database with SQL schema...")

        # Create pgvector extension for PostgreSQL
        if DATABASE_URL.startswith("postgresql"):
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    print("✓ pgvector extension enabled")
            except Exception as e:
                print(f"⚠ Warning: Could not enable pgvector extension: {e}")

        # Execute init.sql to create all tables
        init_sql_path = os.path.join(os.path.dirname(__file__), "init.sql")
        with open(init_sql_path, "r") as f:
            sql_script = f.read()

        with engine.connect() as conn:
            # Execute the SQL script
            conn.execute(text(sql_script))
            conn.commit()

        print("✓ Database initialized successfully with SQL schema")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return False


def fetch_and_add_openrouter_models() -> None:
    """
    Fetch OpenRouter models from API and add to the database.
    Maps OpenRouter API response to AIModel schema.
    """
    import json
    from db.sql_helpers import execute_one, execute_write
    from utils import utc_now

    try:
        with get_raw_connection() as conn:
            models_endpoint = "https://openrouter.ai/api/v1/models"
            response = requests.get(models_endpoint, timeout=10)
            if not response.ok:
                print(f"✗ Failed to fetch OpenRouter models: {response.status_code}")
                return
            models_data = response.json().get("data", [])
            if not models_data:
                print("✗ No model data found in response")
                return

            created_models = []
            updated_models = []

            for model in models_data:
                model_id = model.get("id")
                if not model_id:
                    continue

                # Extract provider from model_id (e.g., "openai/gpt-4" -> "openai")
                provider_parts = model_id.split("/")
                provider = provider_parts[0] if len(provider_parts) > 1 else "openrouter"

                # Check if the model already exists in DB
                check_query = "SELECT id FROM ai_models WHERE model_id = %s"
                existing_model = execute_one(conn, check_query, (model_id,))

                # Extract pricing information
                pricing_info = model.get("pricing", {})
                top_provider_info = model.get("top_provider", {})

                # Get context length from model or top_provider
                context_length = (
                    model.get("context_length")
                    or top_provider_info.get("context_length")
                    or None
                )

                # Extract pricing per million tokens
                input_price = pricing_info.get("prompt") or top_provider_info.get(
                    "input_price_per_million_tokens"
                )
                output_price = pricing_info.get("completion") or top_provider_info.get(
                    "output_price_per_million_tokens"
                )

                if existing_model:
                    # Update existing model with latest data
                    update_query = """
                        UPDATE ai_models
                        SET name = %s, provider = %s, canonical_slug = %s,
                            description = %s, context_length = %s, architecture = %s,
                            pricing = %s, top_provider = %s, per_request_limits = %s,
                            supported_parameters = %s, default_parameters = %s,
                            config = %s, input_price_per_million_tokens = %s,
                            output_price_per_million_tokens = %s, currency = %s,
                            last_price_refresh_at = %s, is_active = %s, updated_at = NOW()
                        WHERE model_id = %s
                    """
                    execute_write(conn, update_query, (
                        model.get("name") or model_id,
                        provider,
                        model.get("id"),
                        model.get("description") or "",
                        context_length,
                        model.get("architecture"),
                        json.dumps(pricing_info) if pricing_info else None,
                        json.dumps(top_provider_info) if top_provider_info else None,
                        json.dumps(model.get("per_request_limits")) if model.get("per_request_limits") else None,
                        json.dumps(model.get("supported_parameters", [])),
                        json.dumps(model.get("default_parameters")) if model.get("default_parameters") else None,
                        json.dumps(model),
                        float(input_price) if input_price else None,
                        float(output_price) if output_price else None,
                        pricing_info.get("currency", "USD") if pricing_info else "USD",
                        utc_now(),
                        True,
                        model_id
                    ))
                    updated_models.append(model.get("name", model_id))
                else:
                    # Create new model
                    insert_query = """
                        INSERT INTO ai_models (
                            name, provider, model_id, canonical_slug, description,
                            context_length, architecture, pricing, top_provider,
                            per_request_limits, supported_parameters, default_parameters,
                            config, input_price_per_million_tokens,
                            output_price_per_million_tokens, currency,
                            last_price_refresh_at, is_active, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """
                    execute_write(conn, insert_query, (
                        model.get("name") or model_id,
                        provider,
                        model_id,
                        model.get("id"),
                        model.get("description") or "",
                        context_length,
                        model.get("architecture"),
                        json.dumps(pricing_info) if pricing_info else None,
                        json.dumps(top_provider_info) if top_provider_info else None,
                        json.dumps(model.get("per_request_limits")) if model.get("per_request_limits") else None,
                        json.dumps(model.get("supported_parameters", [])),
                        json.dumps(model.get("default_parameters")) if model.get("default_parameters") else None,
                        json.dumps(model),
                        float(input_price) if input_price else None,
                        float(output_price) if output_price else None,
                        pricing_info.get("currency", "USD") if pricing_info else "USD",
                        utc_now(),
                        True
                    ))
                    created_models.append(model.get("name", model_id))

            if created_models:
                print(f"✓ Added {len(created_models)} new OpenRouter models")
            if updated_models:
                print(f"✓ Updated {len(updated_models)} existing OpenRouter models")
            if not created_models and not updated_models:
                print("No OpenRouter models added or updated.")
    except Exception as e:
        print(f"✗ Error adding OpenRouter models: {e}")
        import traceback
        traceback.print_exc()


def create_sample_data():
    """
    Create sample data for all tables
    """
    from models import (
        # AI Solver models
        AuthToken,
        ChatMessage,
        ChatSession,
        Commit,
        ContextCard,
        FileEmbedding,
        Issue,
        PullRequest,
        Repository,
        Solve,
        SolveRun,
        SolveStatus,
        User,
        UserIssue,
    )

    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_users = (
            db.query(User)
            .filter(
                User.github_username.in_(
                    ["alice_dev", "bob_coder", "charlie_architect", "demo_user"]
                )
            )
            .all()
        )

        if existing_users:
            print("✓ Sample data already exists, skipping creation")
            print(
                f"Found {len(existing_users)} existing users: {[u.github_username for u in existing_users]}"
            )
            return True

        print("📊 Creating sample data...")

        # Sample data for Users
        sample_users = [
            User(
                github_username="alice_dev",
                github_user_id="12345",
                email="alice@example.com",
                display_name="Alice Developer",
                avatar_url="https://avatars.githubusercontent.com/u/12345?v=4",
            ),
            User(
                github_username="bob_coder",
                github_user_id="67890",
                email="bob@example.com",
                display_name="Bob Coder",
                avatar_url="https://avatars.githubusercontent.com/u/67890?v=4",
            ),
            User(
                github_username="charlie_architect",
                github_user_id="11111",
                email="charlie@example.com",
                display_name="Charlie Architect",
                avatar_url="https://avatars.githubusercontent.com/u/11111?v=4",
            ),
            User(
                github_username="demo_user",
                github_user_id="19365600",
                email="demo@yudai.app",
                display_name="Demo User",
                avatar_url="https://avatars.githubusercontent.com/u/19365600?v=4",
            ),
        ]

        for user in sample_users:
            db.add(user)
        db.commit()

        # Sample AuthTokens
        sample_tokens = [
            AuthToken(
                user_id=1,
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True,
            ),
            AuthToken(
                user_id=2,
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True,
            ),
            AuthToken(
                user_id=4,  # demo_user
                access_token=f"ghp_{uuid.uuid4().hex[:40]}",
                token_type="bearer",
                scope="repo user",
                expires_at=utc_now() + timedelta(days=30),
                is_active=True,
            ),
        ]

        for token in sample_tokens:
            db.add(token)
        db.commit()

        fetch_and_add_openrouter_models()

        # Assign refresh_token after construction to avoid keyword issues
        try:
            if hasattr(AuthToken, "refresh_token"):
                tokens = db.query(AuthToken).order_by(AuthToken.id.asc()).all()
                for t in tokens[-len(sample_tokens) :]:  # best effort: last inserted
                    t.refresh_token = f"ghr_{uuid.uuid4().hex[:40]}"
                db.commit()
        except Exception:
            # Non-fatal: continue without refresh tokens
            db.rollback()

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
                pushed_at=utc_now() - timedelta(days=1),
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
                pushed_at=utc_now() - timedelta(hours=6),
            ),
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
                github_updated_at=utc_now() - timedelta(days=2),
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
                github_closed_at=utc_now() - timedelta(days=1),
            ),
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
                github_updated_at=utc_now() - timedelta(days=1),
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
                author_date=utc_now() - timedelta(days=100),
            ),
            Commit(
                sha="def456abc789123",
                repository_id=1,
                message="Add user authentication feature",
                html_url="https://github.com/alice_dev/awesome-project/commit/def456abc789123",
                author_name="Alice Developer",
                author_email="alice@example.com",
                author_date=utc_now() - timedelta(days=5),
            ),
        ]

        for commit in sample_commits:
            db.add(commit)
        db.commit()

        # Note: FileItem and FileAnalysis models have been removed from models.py
        # Sample data for these models is no longer created
        # The swe_agent_configs / ai_solve_* tables have also been retired;
        # Solve/SolveRun rows now capture solver telemetry end-to-end.

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
                tokens_used=0,
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
                last_activity=utc_now() - timedelta(hours=2),
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
                last_activity=utc_now() - timedelta(minutes=30),
            ),
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
                tokens=20,
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
                processing_time=1200.5,
            ),
            ChatMessage(
                session_id=2,
                message_id="msg_003",
                message_text="Can you help me optimize my React components for better performance?",
                sender_type="user",
                role="user",
                is_code=False,
                tokens=15,
            ),
        ]

        for message in sample_messages:
            db.add(message)
        db.commit()

        # Update session statistics
        db.execute(
            text(
                "UPDATE chat_sessions SET total_messages = 2, total_tokens = 55 WHERE id = 1"
            )
        )
        db.execute(
            text(
                "UPDATE chat_sessions SET total_messages = 1, total_tokens = 15 WHERE id = 2"
            )
        )
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
                tokens=150,
            ),
            ContextCard(
                user_id=1,
                session_id=1,
                title="Flask-OAuthlib Example",
                description="Code example for Flask OAuth integration",
                content="```python\nfrom flask_oauthlib.client import OAuth\n\noauth = OAuth(app)\n```",
                source="chat",
                tokens=75,
                is_active=True,
            ),
            ContextCard(
                user_id=2,
                session_id=2,
                title="React Performance Tips",
                description="Best practices for React optimization",
                content="1. Use React.memo for functional components\n2. Implement useMemo for expensive calculations\n3. Use useCallback for function references",
                source="chat",
                tokens=120,
            ),
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
                file_metadata='{"size": 500, "encoding": "utf-8", "lines": 6}',
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
                file_metadata='{"size": 200, "encoding": "utf-8", "lines": 3}',
            ),
        ]

        for file_embedding in sample_file_embeddings:
            db.add(file_embedding)
        db.commit()

        # Fetch and add OpenRouter models (called separately after sample data)
        # This ensures models are available for the solver
        fetch_and_add_openrouter_models()

        # Sample Solve jobs for solver orchestration
        sample_solves = [
            Solve(
                id="demo-solve-1",
                user_id=1,
                session_id=1,
                repo_url="https://github.com/alice_dev/awesome-project",
                issue_number=1,
                base_branch="main",
                status=SolveStatus.COMPLETED.value,
                matrix={
                    "experiments": [
                        {"model": "anthropic/claude-3.5-sonnet", "temperature": 0.1}
                    ]
                },
                limits={"max_parallel": 1, "time_budget_s": 3600},
                requested_by="demo_user",
                champion_run_id="demo-solve-run-1",
                max_parallel=1,
                time_budget_s=3600,
                started_at=utc_now() - timedelta(hours=5),
                completed_at=utc_now() - timedelta(hours=3),
            ),
            Solve(
                id="demo-solve-2",
                user_id=2,
                session_id=2,
                repo_url="https://github.com/bob_coder/cool-app",
                issue_number=2,
                base_branch="develop",
                status=SolveStatus.RUNNING.value,
                matrix={
                    "experiments": [{"model": "openai/gpt-4-turbo", "temperature": 0.2}]
                },
                limits={"max_parallel": 2, "time_budget_s": 5400},
                requested_by="demo_user",
                max_parallel=2,
                time_budget_s=5400,
                started_at=utc_now() - timedelta(hours=1),
            ),
        ]

        for solve in sample_solves:
            db.add(solve)
        db.commit()

        sample_solve_runs = [
            SolveRun(
                id="demo-solve-run-1",
                solve_id="demo-solve-1",
                model="anthropic/claude-3.5-sonnet",
                temperature=0.1,
                max_edits=5,
                evolution="baseline",
                status=SolveStatus.COMPLETED.value,
                sandbox_id="sbx-1234",
                pr_url="https://github.com/alice_dev/awesome-project/pull/5",
                tests_passed=True,
                loc_changed=120,
                files_changed=5,
                tokens=18000,
                latency_ms=720000,
                diagnostics={"notes": "All tests passed"},
                started_at=utc_now() - timedelta(hours=4),
                completed_at=utc_now() - timedelta(hours=3, minutes=30),
            ),
            SolveRun(
                id="demo-solve-run-2",
                solve_id="demo-solve-2",
                model="openai/gpt-4-turbo",
                temperature=0.2,
                max_edits=4,
                evolution="baseline",
                status=SolveStatus.RUNNING.value,
                sandbox_id="sbx-5678",
                tests_passed=None,
                loc_changed=None,
                files_changed=None,
                tokens=None,
                latency_ms=None,
                diagnostics={"notes": "Run in progress"},
                started_at=utc_now() - timedelta(minutes=45),
            ),
        ]

        for solve_run in sample_solve_runs:
            db.add(solve_run)
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
        sample_users = (
            db.query(User).filter(User.github_username.in_(sample_usernames)).all()
        )

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
