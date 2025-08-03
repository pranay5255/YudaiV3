#!/usr/bin/env python3
"""
Enhanced test script to verify database initialization and connectivity
Works both locally and in Docker containers
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def get_database_url():
    """Get database URL from environment or use defaults"""
    # Check if we're in Docker (DATABASE_URL should be set)
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    
    # Check if we're in Docker Compose (use 'db' as host)
    if os.getenv("DOCKER_COMPOSE"):
        return "postgresql://yudai_user:yudai_password@db:5432/yudai_dev"
    
    # Local development (use localhost)
    return "postgresql://yudai_user:yudai_password@localhost:5432/yudai_dev"

def test_database():
    """Test database connection and verify tables exist"""
    database_url = get_database_url()
    
    print("🔍 Testing database connection...")
    print(f"   URL: {database_url}")
    
    try:
        # Connect to database
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            echo=False
        )
        
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
            
            # Check if tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = [
                'users', 'auth_tokens', 'repositories', 'file_items', 
                'file_analyses', 'context_cards', 'idea_items', 'chat_sessions', 
                'chat_messages', 'user_issues', 'issues', 'pull_requests', 'commits'
            ]
            
            print(f"✓ Found {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
            # Check for expected tables
            missing_tables = [table for table in expected_tables if table not in tables]
            if missing_tables:
                print(f"⚠ Missing tables: {missing_tables}")
                return False
            
            # Check sample data
            print("\n📊 Checking sample data...")
            
            # Check users
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"✓ Users: {user_count}")
            
            # Check repositories
            result = conn.execute(text("SELECT COUNT(*) FROM repositories"))
            repo_count = result.scalar()
            print(f"✓ Repositories: {repo_count}")
            
            # Check issues
            result = conn.execute(text("SELECT COUNT(*) FROM issues"))
            issue_count = result.scalar()
            print(f"✓ Issues: {issue_count}")
            
            # Check context cards
            result = conn.execute(text("SELECT COUNT(*) FROM context_cards"))
            card_count = result.scalar()
            print(f"✓ Context Cards: {card_count}")
            
            # Check chat sessions
            result = conn.execute(text("SELECT COUNT(*) FROM chat_sessions"))
            session_count = result.scalar()
            print(f"✓ Chat Sessions: {session_count}")
            
            print("\n✅ Database initialization test passed!")
            return True
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        print("🔍 Debug information:")
        print(f"   - Database URL: {database_url}")
        print(f"   - Environment: {'Docker' if os.getenv('DATABASE_URL') else 'Local'}")
        print(f"   - Current working directory: {os.getcwd()}")
        print(f"   - Python path: {sys.path[:3]}...")
        return False

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1) 