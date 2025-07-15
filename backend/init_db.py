#!/usr/bin/env python3
"""
Database initialization script for YudaiV3
This script creates all tables and adds a default user for testing
"""

import os
import sys
from sqlalchemy.orm import Session

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.database import init_db, SessionLocal
from models import User

def create_default_user():
    """Create a default user for testing if it doesn't exist."""
    db = SessionLocal()
    try:
        # Check if default user exists
        default_user = db.query(User).filter(User.github_username == "test_user").first()
        
        if not default_user:
            # Create default user
            default_user = User(
                github_username="test_user",
                github_user_id="12345",
                email="test@example.com",
                display_name="Test User"
            )
            db.add(default_user)
            db.commit()
            print("✅ Created default test user")
        else:
            print("✅ Default test user already exists")
            
    except Exception as e:
        print(f"❌ Error creating default user: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main initialization function."""
    print("�� Initializing YudaiV3 database...")
    
    try:
        # Initialize database tables
        init_db()
        print("✅ Database tables created successfully")
        
        # Create default user
        create_default_user()
        
        print("🎉 Database initialization completed!")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 