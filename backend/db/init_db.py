#!/usr/bin/env python3
"""
Database initialization script for YudaiV3
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from db import init_db, engine
from sqlalchemy import text

def create_database():
    """Create the database and initialize all tables"""
    try:
        print("Initializing database...")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
        
        # Create all tables
        init_db()
        print("✓ Database tables created successfully")
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"✓ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
        
        return True
        
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False

def check_database_health():
    """Check database health and connectivity"""
    try:
        with engine.connect() as conn:
            # Check if we can connect
            conn.execute(text("SELECT 1"))
            
            # Check if tables exist
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['users', 'auth_tokens', 'repositories', 'file_items', 'file_analyses', 'context_cards', 'idea_items', 'chat_sessions', 'chat_messages', 'user_issues']
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
    
    args = parser.parse_args()
    
    if args.check:
        check_database_health()
    elif args.init:
        create_database()
    else:
        print("Usage: python init_db.py --init | --check")
        sys.exit(1) 