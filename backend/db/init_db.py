#!/usr/bin/env python3
"""
Database initialization script for YudaiV3.
This script can work both with and without the application models.
All timestamps are stored as timezone-aware UTC values.
"""

import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def wait_for_database(max_retries=30, delay=2):
    """Wait for database to be ready"""
    print("Waiting for database to be ready...")
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                os.getenv("DATABASE_URL"),
                pool_pre_ping=True
            )
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("SELECT 1"))
            print("✓ Database is ready!")
            return engine
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database not ready yet (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(delay)
            else:
                print(f"✗ Database connection failed after {max_retries} attempts")
                raise
    return None

def create_tables_with_models(engine):
    """Create tables using SQLAlchemy models (preferred method)"""
    try:
        from db.database import init_db
        print("Creating tables using SQLAlchemy models...")
        init_db()
        print("✓ Tables created successfully using models")
        return True
        
    except ImportError as e:
        print(f"Could not import models: {e}")
        print("Falling back to standalone table creation...")
        return False

def create_tables_standalone(engine):
    """Create all tables using raw SQL (fallback method) - matches models.py exactly"""
    print("Creating tables using standalone SQL...")
    
    # SQL statements to create tables - EXACTLY matching models.py schema
    create_tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            github_username VARCHAR(255) UNIQUE NOT NULL,
            github_user_id VARCHAR(255) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            display_name VARCHAR(255),
            avatar_url VARCHAR(500),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            last_login TIMESTAMP WITH TIME ZONE
        );
        
        CREATE TABLE IF NOT EXISTS github_app_installations (
            id SERIAL PRIMARY KEY,
            github_installation_id INTEGER NOT NULL UNIQUE,
            github_app_id VARCHAR(50) NOT NULL,
            account_type VARCHAR(20) NOT NULL,
            account_login VARCHAR(255) NOT NULL,
            account_id INTEGER NOT NULL,
            permissions JSONB,
            events JSONB,
            repository_selection VARCHAR(20) DEFAULT 'all',
            single_file_name VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            suspended_at TIMESTAMP WITH TIME ZONE,
            suspended_by VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            access_token VARCHAR(500) NOT NULL,
            refresh_token VARCHAR(500),
            token_type VARCHAR(50) DEFAULT 'bearer',
            scope VARCHAR(500),
            expires_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN DEFAULT TRUE,
            github_app_id VARCHAR(50),
            installation_id INTEGER REFERENCES github_app_installations(github_installation_id),
            permissions JSONB,
            repositories_url VARCHAR(500),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS session_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            github_repo_id INTEGER,
            name VARCHAR(255) NOT NULL,
            owner VARCHAR(255) NOT NULL,
            full_name VARCHAR(512) NOT NULL,
            repo_url VARCHAR(500),
            description TEXT,
            private BOOLEAN DEFAULT FALSE,
            html_url VARCHAR(500) NOT NULL,
            clone_url VARCHAR(500) NOT NULL,
            language VARCHAR(100),
            stargazers_count INTEGER DEFAULT 0,
            forks_count INTEGER DEFAULT 0,
            open_issues_count INTEGER DEFAULT 0,
            default_branch VARCHAR(100),
            github_created_at TIMESTAMP WITH TIME ZONE,
            github_updated_at TIMESTAMP WITH TIME ZONE,
            pushed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            github_issue_id INTEGER UNIQUE NOT NULL,
            repository_id INTEGER REFERENCES repositories(id),
            number INTEGER NOT NULL,
            title VARCHAR(1000) NOT NULL,
            body TEXT,
            state VARCHAR(50) NOT NULL,
            html_url VARCHAR(1000) NOT NULL,
            author_username VARCHAR(255),
            github_created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            github_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            github_closed_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pull_requests (
            id SERIAL PRIMARY KEY,
            github_pr_id INTEGER UNIQUE NOT NULL,
            repository_id INTEGER REFERENCES repositories(id),
            number INTEGER NOT NULL,
            title VARCHAR(1000) NOT NULL,
            body TEXT,
            state VARCHAR(50) NOT NULL,
            html_url VARCHAR(1000) NOT NULL,
            author_username VARCHAR(255),
            github_created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            github_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            github_closed_at TIMESTAMP WITH TIME ZONE,
            merged_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commits (
            id SERIAL PRIMARY KEY,
            sha VARCHAR(40) UNIQUE NOT NULL,
            repository_id INTEGER REFERENCES repositories(id),
            message TEXT NOT NULL,
            html_url VARCHAR(1000) NOT NULL,
            author_name VARCHAR(255),
            author_email VARCHAR(255),
            author_date TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_issues (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            issue_id VARCHAR(255) UNIQUE NOT NULL,
            context_card_id INTEGER,
            issue_text_raw TEXT NOT NULL,
            issue_steps JSON,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            session_id VARCHAR(255),
            context_cards JSON,
            ideas JSON,
            repo_owner VARCHAR(255),
            repo_name VARCHAR(255),
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(50) DEFAULT 'pending',
            agent_response TEXT,
            processing_time FLOAT,
            tokens_used INTEGER DEFAULT 0,
            github_issue_url VARCHAR(1000),
            github_issue_number INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            processed_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS oauth_states (
            state VARCHAR(255) PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            github_app_id VARCHAR(50),
            user_id INTEGER REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_id VARCHAR(255) UNIQUE NOT NULL,
            title VARCHAR(255),
            description TEXT,
            repo_owner VARCHAR(255),
            repo_name VARCHAR(255),
            repo_branch VARCHAR(255) DEFAULT 'main',
            repo_context JSON,
            is_active BOOLEAN DEFAULT TRUE,
            total_messages INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            last_activity TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS file_embeddings (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
            repository_id INTEGER REFERENCES repositories(id),
            file_path VARCHAR(1000) NOT NULL,
            file_name VARCHAR(500) NOT NULL,
            file_type VARCHAR(100) NOT NULL,
            file_content TEXT,
            embedding VECTOR(384),  -- sentence-transformers/all-MiniLM-L6-v2 dimensions
            chunk_index INTEGER DEFAULT 0,
            chunk_text TEXT NOT NULL,
            tokens INTEGER DEFAULT 0,
            session_tokens_used INTEGER DEFAULT 0,
            file_metadata JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
            message_id VARCHAR(255) NOT NULL,
            message_text TEXT NOT NULL,
            sender_type VARCHAR(50) NOT NULL,
            role VARCHAR(50) NOT NULL,
            is_code BOOLEAN DEFAULT FALSE,
            tokens INTEGER DEFAULT 0,
            model_used VARCHAR(100),
            processing_time FLOAT,
            context_cards JSON,
            referenced_files JSON,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS context_cards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            content TEXT NOT NULL,
            source VARCHAR(50) NOT NULL,
            tokens INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """
    ]
    
    # Indexes matching models.py relationships and performance requirements
    create_indexes_sql = [
        # User indexes
        "CREATE INDEX IF NOT EXISTS idx_users_github_username ON users(github_username)",
        "CREATE INDEX IF NOT EXISTS idx_users_github_user_id ON users(github_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        
        # Auth token indexes
        "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_auth_tokens_is_active ON auth_tokens(is_active)",
        
        # Session token indexes
        "CREATE INDEX IF NOT EXISTS idx_session_tokens_session_token ON session_tokens(session_token)",
        "CREATE INDEX IF NOT EXISTS idx_session_tokens_user_id ON session_tokens(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_tokens_is_active ON session_tokens(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_session_tokens_expires_at ON session_tokens(expires_at)",
        
        # Repository indexes
        "CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_repositories_github_repo_id ON repositories(github_repo_id)",
        "CREATE INDEX IF NOT EXISTS idx_repositories_owner ON repositories(owner)",
        "CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name)",
        "CREATE INDEX IF NOT EXISTS idx_repositories_repo_url ON repositories(repo_url)",
        
        # Issue indexes
        "CREATE INDEX IF NOT EXISTS idx_issues_github_issue_id ON issues(github_issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_issues_repository_id ON issues(repository_id)",
        
        # Pull request indexes
        "CREATE INDEX IF NOT EXISTS idx_pull_requests_github_pr_id ON pull_requests(github_pr_id)",
        "CREATE INDEX IF NOT EXISTS idx_pull_requests_repository_id ON pull_requests(repository_id)",
        
        # Commit indexes
        "CREATE INDEX IF NOT EXISTS idx_commits_sha ON commits(sha)",
        "CREATE INDEX IF NOT EXISTS idx_commits_repository_id ON commits(repository_id)",
        
        
        # User issue indexes
        "CREATE INDEX IF NOT EXISTS idx_user_issues_user_id ON user_issues(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_issues_issue_id ON user_issues(issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_issues_session_id ON user_issues(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_issues_status ON user_issues(status)",
        
        # File embedding indexes
        "CREATE INDEX IF NOT EXISTS idx_file_embeddings_session_id ON file_embeddings(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_embeddings_repository_id ON file_embeddings(repository_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_embeddings_file_path ON file_embeddings(file_path)",
        # Vector index for similarity search (using IVFFlat for cosine distance)
        "CREATE INDEX IF NOT EXISTS idx_file_embeddings_embedding ON file_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)",
        
        # Chat session indexes
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_repo_owner ON chat_sessions(repo_owner)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_repo_name ON chat_sessions(repo_name)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_is_active ON chat_sessions(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_activity ON chat_sessions(last_activity)",
        
        # Chat message indexes
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_message_id ON chat_messages(message_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_type ON chat_messages(sender_type)",
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at)",
        
        # Context card indexes
        "CREATE INDEX IF NOT EXISTS idx_context_cards_user_id ON context_cards(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_cards_session_id ON context_cards(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_cards_source ON context_cards(source)",
        "CREATE INDEX IF NOT EXISTS idx_context_cards_is_active ON context_cards(is_active)",
        
        # OAuth state indexes
        "CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states(expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_oauth_states_is_used ON oauth_states(is_used)"
    ]
    
    with engine.connect() as conn:
        for sql in create_tables_sql:
            conn.execute(text(sql))
        
        # Create indexes after tables
        for sql in create_indexes_sql:
            conn.execute(text(sql))
        
        conn.commit()
    
    print("✓ Tables and indexes created successfully using standalone SQL")

def create_sample_data_with_models(engine):
    """Create sample data using SQLAlchemy models (preferred method)"""
    try:
        from db import create_sample_data
        print("Creating sample data using SQLAlchemy models...")
        create_sample_data()
        print("✓ Sample data created successfully using models")
        return True
        
    except ImportError as e:
        print(f"Could not import sample data function: {e}")
        print("Falling back to standalone sample data creation...")
        return False

def create_sample_data_standalone(engine):
    """Insert sample data using raw SQL (fallback method)"""
    print("Creating sample data using standalone SQL...")
    
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Sample Users
        db.execute(text("""
            INSERT INTO users (github_username, github_user_id, email, display_name, avatar_url, created_at, updated_at) VALUES
            ('alice_dev', '12345', 'alice@example.com', 'Alice Developer', 'https://avatars.githubusercontent.com/u/12345?v=4', NOW(), NOW()),
            ('bob_coder', '67890', 'bob@example.com', 'Bob Coder', 'https://avatars.githubusercontent.com/u/67890?v=4', NOW(), NOW())
            ON CONFLICT (github_username) DO NOTHING
        """))
        
        # Sample Repositories
        db.execute(text("""
            INSERT INTO repositories (user_id, github_repo_id, name, owner, full_name, repo_url, description, private, html_url, clone_url, language, stargazers_count, forks_count, open_issues_count, github_created_at, github_updated_at, pushed_at, created_at, updated_at) VALUES
            (1, 123456789, 'awesome-project', 'alice_dev', 'alice_dev/awesome-project', 'https://github.com/alice_dev/awesome-project', 'An awesome project for demonstrating features', false, 'https://github.com/alice_dev/awesome-project', 'https://github.com/alice_dev/awesome-project.git', 'Python', 42, 5, 3, NOW() - INTERVAL '100 days', NOW() - INTERVAL '5 days', NOW() - INTERVAL '1 day', NOW(), NOW())
            ON CONFLICT (github_repo_id) DO NOTHING
        """))
        
        
        # Sample User Issues
        db.execute(text("""
            INSERT INTO user_issues (user_id, issue_id, title, description, issue_text_raw, priority, status, tokens_used, created_at, updated_at) VALUES
            (1, 'issue_001', 'Implement OAuth2 Authentication', 'Need to implement secure OAuth2 authentication flow', 'Please implement OAuth2 authentication for our application', 'medium', 'pending', 0, NOW(), NOW())
            ON CONFLICT (issue_id) DO NOTHING
        """))
        
        db.commit()
        print("✓ Sample data created successfully using standalone SQL")
        
    except Exception as e:
        print(f"✗ Error inserting sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_database():
    """Create the database and initialize all tables"""
    try:
        print("🏗️  Initializing YudaiV3 database...")
        
        # Wait for database to be ready
        engine = wait_for_database()
        if not engine:
            print("❌ Could not connect to database")
            return False
        
        # Always try SQLAlchemy models first (preferred for consistency)
        print("🏗️  Attempting SQLAlchemy model-based initialization...")
        if create_tables_with_models(engine):
            print("✅ Using SQLAlchemy models for table creation")
        else:
            print("⚠️  Falling back to standalone SQL for table creation")
            create_tables_standalone(engine)
        
        # Create sample data (models preferred)
        print("📊 Creating sample data...")
        if create_sample_data_with_models(engine):
            print("✅ Using SQLAlchemy models for sample data")
        else:
            print("⚠️  Falling back to standalone SQL for sample data")
            create_sample_data_standalone(engine)
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  ✓ {table}")
        
        # Check database health
        check_database_health()
        
        print("\n" + "="*50)
        print("🎉 DATABASE INITIALIZATION COMPLETE")
        print("   ✓ Tables created with basic indexes")
        print("   ✓ Sample data populated for testing")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: Database initialization failed: {e}")
        print("🔍 This may be due to:")
        print("   - Database connection issues")
        print("   - Schema conflicts")
        print("   - Missing dependencies")
        return False

def create_sample_data_wrapper():
    """Wrapper function to create sample data"""
    try:
        print("Creating sample data...")
        
        # Wait for database to be ready
        engine = wait_for_database()
        if not engine:
            return False
        
        # Try to create sample data using models first, fall back to standalone if needed
        if not create_sample_data_with_models(engine):
            create_sample_data_standalone(engine)
        
        return True
        
    except Exception as e:
        print(f"✗ Sample data creation failed: {e}")
        return False

def check_database_health():
    """Check database health and connectivity"""
    try:
        engine = wait_for_database(max_retries=5)
        if not engine:
            return False
            
        with engine.connect() as conn:
            # Check if we can connect
            conn.execute(text("SELECT 1"))
            
            # Check if tables exist - updated to match models.py
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = [
                'users', 'auth_tokens', 'session_tokens', 'repositories',
                'issues', 'pull_requests', 'commits', 'user_issues', 'file_embeddings', 'oauth_states',
                'chat_sessions', 'chat_messages', 'context_cards'
            ]
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                print(f"⚠ Missing tables: {missing_tables}")
                return False
            
            print("✓ Database health check passed")
            return True
            
    except Exception as e:
        print(f"✗ Database health check failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument("--check", action="store_true", help="Check database health")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--sample-data", action="store_true", help="Create sample data")
    parser.add_argument("--full-init", action="store_true", help="Initialize database and create sample data")
    
    args = parser.parse_args()
    
    if args.check:
        check_database_health()
    elif args.init:
        create_database()
    elif args.sample_data:
        create_sample_data_wrapper()
    elif args.full_init:
        if create_database():
            create_sample_data_wrapper()
    else:
        print("Usage: python init_db.py --init | --check | --sample-data | --full-init")
        sys.exit(1) 