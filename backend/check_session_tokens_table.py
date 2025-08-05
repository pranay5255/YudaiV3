#!/usr/bin/env python3
"""
Check and create session_tokens table if it doesn't exist
"""

import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from db.database import get_db
from sqlalchemy import text


def check_and_create_session_tokens_table():
    """Check if session_tokens table exists and create it if needed"""
    print("Checking session_tokens table...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check if session_tokens table exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'session_tokens'
            );
        """))
        
        table_exists = result.scalar()
        
        if table_exists:
            print("✓ session_tokens table already exists")
            return True
        else:
            print("✗ session_tokens table does not exist, creating it...")
            
            # Create the session_tokens table
            db.execute(text("""
                CREATE TABLE session_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            """))
            
            # Create indexes
            db.execute(text("""
                CREATE INDEX idx_session_tokens_session_token ON session_tokens(session_token);
                CREATE INDEX idx_session_tokens_user_id ON session_tokens(user_id);
                CREATE INDEX idx_session_tokens_is_active ON session_tokens(is_active);
                CREATE INDEX idx_session_tokens_expires_at ON session_tokens(expires_at);
            """))
            
            db.commit()
            print("✓ session_tokens table created successfully")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = check_and_create_session_tokens_table()
    sys.exit(0 if success else 1) 