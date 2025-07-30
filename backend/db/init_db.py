#!/usr/bin/env python3
"""
Database initialization script for YudaiV3
This script can work both with and without the application models
"""

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
            # Use Unix socket connection instead of TCP/IP
            engine = create_engine(
                "postgresql://yudai_user:yudai_password@/yudai_db?host=/var/run/postgresql",
                pool_pre_ping=True
            )
            with engine.connect() as conn:
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
        from db import init_db
        # Import models but don't use Base directly
        
        print("Creating tables using SQLAlchemy models...")
        init_db()
        print("✓ Tables created successfully using models")
        return True
        
    except ImportError as e:
        print(f"Could not import models: {e}")
        print("Falling back to standalone table creation...")
        return False

def create_tables_standalone(engine):
    """Create all tables using raw SQL (fallback method)"""
    print("Creating tables using standalone SQL...")
    
    # SQL statements to create tables
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
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id SERIAL PRIMARY KEY,
            github_repo_id INTEGER UNIQUE,
            user_id INTEGER REFERENCES users(id),
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
        CREATE TABLE IF NOT EXISTS file_items (
            id SERIAL PRIMARY KEY,
            repository_id INTEGER REFERENCES repositories(id),
            name VARCHAR(500) NOT NULL,
            path VARCHAR(1000) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            category VARCHAR(100) NOT NULL,
            tokens INTEGER DEFAULT 0,
            is_directory BOOLEAN DEFAULT FALSE,
            parent_id INTEGER REFERENCES file_items(id),
            content TEXT,
            content_size INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS file_analyses (
            id SERIAL PRIMARY KEY,
            repository_id INTEGER REFERENCES repositories(id),
            raw_data JSON,
            processed_data JSON,
            total_files INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            max_file_size INTEGER,
            status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            processed_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS context_cards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            content TEXT NOT NULL,
            source VARCHAR(50) NOT NULL,
            tokens INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS idea_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            complexity VARCHAR(10) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            session_id VARCHAR(255) UNIQUE NOT NULL,
            title VARCHAR(255),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            total_messages INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            last_activity TIMESTAMP WITH TIME ZONE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES chat_sessions(id),
            message_id VARCHAR(255) UNIQUE NOT NULL,
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
        CREATE TABLE IF NOT EXISTS user_issues (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            issue_id VARCHAR(255) UNIQUE NOT NULL,
            context_card_id INTEGER REFERENCES context_cards(id),
            issue_text_raw TEXT NOT NULL,
            issue_steps JSON,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            conversation_id VARCHAR(255),
            chat_session_id INTEGER REFERENCES chat_sessions(id),
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
        """
    ]
    
    with engine.connect() as conn:
        for sql in create_tables_sql:
            conn.execute(text(sql))
        conn.commit()
    
    print("✓ Tables created successfully using standalone SQL")

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
            ('bob_coder', '67890', 'bob@example.com', 'Bob Coder', 'https://avatars.githubusercontent.com/u/67890?v=4', NOW(), NOW()),
            ('charlie_architect', '11111', 'charlie@example.com', 'Charlie Architect', 'https://avatars.githubusercontent.com/u/11111?v=4', NOW(), NOW())
            ON CONFLICT (github_username) DO NOTHING
        """))
        
        # Sample AuthTokens
        db.execute(text("""
            INSERT INTO auth_tokens (user_id, access_token, refresh_token, token_type, scope, expires_at, is_active, created_at, updated_at) VALUES
            (1, 'ghp_sample_access_token_1', 'ghr_sample_refresh_token_1', 'bearer', 'repo user', NOW() + INTERVAL '30 days', true, NOW(), NOW()),
            (2, 'ghp_sample_access_token_2', 'ghr_sample_refresh_token_2', 'bearer', 'repo user', NOW() + INTERVAL '30 days', true, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """))
        
        # Sample Repositories
        db.execute(text("""
            INSERT INTO repositories (github_repo_id, user_id, name, owner, full_name, repo_url, description, private, html_url, clone_url, language, stargazers_count, forks_count, open_issues_count, github_created_at, github_updated_at, pushed_at, created_at, updated_at) VALUES
            (123456789, 1, 'awesome-project', 'alice_dev', 'alice_dev/awesome-project', 'https://github.com/alice_dev/awesome-project', 'An awesome project for demonstrating features', false, 'https://github.com/alice_dev/awesome-project', 'https://github.com/alice_dev/awesome-project.git', 'Python', 42, 5, 3, NOW() - INTERVAL '100 days', NOW() - INTERVAL '5 days', NOW() - INTERVAL '1 day', NOW(), NOW()),
            (987654321, 2, 'cool-app', 'bob_coder', 'bob_coder/cool-app', 'https://github.com/bob_coder/cool-app', 'A cool application with modern features', false, 'https://github.com/bob_coder/cool-app', 'https://github.com/bob_coder/cool-app.git', 'TypeScript', 15, 2, 1, NOW() - INTERVAL '50 days', NOW() - INTERVAL '2 days', NOW() - INTERVAL '6 hours', NOW(), NOW())
            ON CONFLICT (github_repo_id) DO NOTHING
        """))
        
        # Sample Issues
        db.execute(text("""
            INSERT INTO issues (github_issue_id, repository_id, number, title, body, state, html_url, author_username, github_created_at, github_updated_at, github_closed_at) VALUES
            (1001, 1, 1, 'Add user authentication feature', 'We need to implement user authentication with OAuth2', 'open', 'https://github.com/alice_dev/awesome-project/issues/1', 'alice_dev', NOW() - INTERVAL '10 days', NOW() - INTERVAL '2 days', NULL),
            (1002, 1, 2, 'Fix database connection issue', 'Database connection is failing in production', 'closed', 'https://github.com/alice_dev/awesome-project/issues/2', 'bob_coder', NOW() - INTERVAL '15 days', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
            ON CONFLICT (github_issue_id) DO NOTHING
        """))
        
        # Sample Pull Requests
        db.execute(text("""
            INSERT INTO pull_requests (github_pr_id, repository_id, number, title, body, state, html_url, author_username, github_created_at, github_updated_at, github_closed_at, merged_at) VALUES
            (2001, 1, 1, 'Implement user authentication', 'This PR adds OAuth2 authentication to the application', 'open', 'https://github.com/alice_dev/awesome-project/pull/1', 'alice_dev', NOW() - INTERVAL '5 days', NOW() - INTERVAL '1 day', NULL, NULL)
            ON CONFLICT (github_pr_id) DO NOTHING
        """))
        
        # Sample Commits
        db.execute(text("""
            INSERT INTO commits (sha, repository_id, message, html_url, author_name, author_email, author_date) VALUES
            ('abc123def456789', 1, 'Initial commit: Add project structure', 'https://github.com/alice_dev/awesome-project/commit/abc123def456789', 'Alice Developer', 'alice@example.com', NOW() - INTERVAL '100 days'),
            ('def456abc789123', 1, 'Add user authentication feature', 'https://github.com/alice_dev/awesome-project/commit/def456abc789123', 'Alice Developer', 'alice@example.com', NOW() - INTERVAL '5 days')
            ON CONFLICT (sha) DO NOTHING
        """))
        
        # Sample FileItems
        db.execute(text("""
            INSERT INTO file_items (repository_id, name, path, file_type, category, tokens, is_directory, parent_id, content, content_size, created_at, updated_at) VALUES
            (1, 'main.py', 'src/main.py', 'INTERNAL', 'Source Code', 1500, false, NULL, '# Main application file

def main():
    print(''Hello, World!'')

if __name__ == ''__main__'':
    main()', 5000, NOW(), NOW()),
            (1, 'requirements.txt', 'requirements.txt', 'INTERNAL', 'Dependencies', 200, false, NULL, 'flask==2.0.1
sqlalchemy==1.4.23
requests==2.26.0', 500, NOW(), NOW()),
            (1, 'src', 'src', 'INTERNAL', 'Directory', 0, true, NULL, NULL, 0, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """))
        
        # Sample FileAnalysis
        db.execute(text("""
            INSERT INTO file_analyses (repository_id, raw_data, processed_data, total_files, total_tokens, max_file_size, status, error_message, created_at, updated_at, processed_at) VALUES
            (1, '{"total_files": 15, "languages": {"Python": 10, "JavaScript": 5}}', '{"analysis": "complete", "complexity": "medium"}', 15, 25000, 10000, 'completed', NULL, NOW(), NOW(), NOW() - INTERVAL '1 day')
            ON CONFLICT DO NOTHING
        """))
        
        # Sample ContextCards
        db.execute(text("""
            INSERT INTO context_cards (user_id, title, description, content, source, tokens, is_active, created_at, updated_at) VALUES
            (1, 'Authentication System Design', 'Design patterns for implementing OAuth2 authentication', 'The authentication system should use OAuth2 with JWT tokens...', 'chat', 800, true, NOW(), NOW()),
            (1, 'Database Schema', 'User and session management database schema', 'CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(255)...', 'file-deps', 600, true, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """))
        
        # Sample IdeaItems
        db.execute(text("""
            INSERT INTO idea_items (user_id, title, description, complexity, status, is_active, created_at, updated_at) VALUES
            (1, 'Add real-time notifications', 'Implement WebSocket-based real-time notifications for user actions', 'M', 'pending', true, NOW(), NOW()),
            (1, 'Implement caching layer', 'Add Redis caching to improve application performance', 'L', 'pending', true, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """))
        
        # Sample ChatSessions
        db.execute(text("""
            INSERT INTO chat_sessions (user_id, session_id, title, description, is_active, total_messages, total_tokens, created_at, updated_at, last_activity) VALUES
            (1, 'session_001', 'Authentication Discussion', 'Discussion about implementing OAuth2 authentication', true, 5, 1200, NOW(), NOW(), NOW() - INTERVAL '2 hours'),
            (2, 'session_002', 'Database Design', 'Planning the database schema for the new feature', true, 3, 800, NOW(), NOW(), NOW() - INTERVAL '1 hour')
            ON CONFLICT (session_id) DO NOTHING
        """))
        
        # Sample ChatMessages
        db.execute(text("""
            INSERT INTO chat_messages (session_id, message_id, message_text, sender_type, role, is_code, tokens, model_used, processing_time, context_cards, referenced_files, error_message, created_at, updated_at) VALUES
            (1, 'msg_001', 'How should we implement OAuth2 authentication?', 'user', 'user', false, 15, 'gpt-4', 1.2, NULL, NULL, NULL, NOW(), NOW()),
            (1, 'msg_002', 'I recommend using the OAuth2 authorization code flow with PKCE for security...', 'assistant', 'assistant', false, 45, 'gpt-4', 2.1, NULL, NULL, NULL, NOW(), NOW())
            ON CONFLICT (message_id) DO NOTHING
        """))
        
        # Sample UserIssues
        db.execute(text("""
            INSERT INTO user_issues (user_id, issue_id, context_card_id, issue_text_raw, issue_steps, title, description, conversation_id, chat_session_id, context_cards, ideas, repo_owner, repo_name, priority, status, agent_response, processing_time, tokens_used, github_issue_url, github_issue_number, created_at, updated_at, processed_at) VALUES
            (1, 'issue_001', 1, 'Need help implementing OAuth2 authentication', '["Set up OAuth2 provider", "Implement callback handler", "Add JWT token validation"]', 'OAuth2 Authentication Implementation', 'Help needed to implement OAuth2 authentication flow', 'conv_001', 1, '["card_001", "card_002"]', '["idea_001"]', 'alice_dev', 'awesome-project', 'high', 'pending', NULL, NULL, 0, NULL, NULL, NOW(), NOW(), NULL)
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
        print("Initializing database...")
        
        # Wait for database to be ready
        engine = wait_for_database()
        if not engine:
            return False
        
        # Try to create tables using models first, fall back to standalone if needed
        if not create_tables_with_models(engine):
            create_tables_standalone(engine)
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"✓ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
        
        return True
        
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
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
            
            # Check if tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['users', 'auth_tokens', 'repositories', 'file_items', 'file_analyses', 'context_cards', 'idea_items', 'chat_sessions', 'chat_messages', 'user_issues', 'issues', 'pull_requests', 'commits']
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