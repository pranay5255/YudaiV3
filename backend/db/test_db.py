#!/usr/bin/env python3
"""
Test script to verify database initialization
"""

import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect

def test_database():
    """Test database connection and verify tables exist"""
    try:
        # Connect to database
        engine = create_engine(
            "postgresql://yudai_user:yudai_password@localhost:5432/yudai_db",
            pool_pre_ping=True
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
            for table in tables:
                print(f"  - {table}")
            
            # Check for expected tables
            missing_tables = [table for table in expected_tables if table not in tables]
            if missing_tables:
                print(f"⚠ Missing tables: {missing_tables}")
                return False
            
            # Check sample data
            print("\nChecking sample data...")
            
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
            
            print("\n✓ Database initialization test passed!")
            return True
            
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1) 