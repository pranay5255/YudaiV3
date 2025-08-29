#!/usr/bin/env python3
"""
Test script to verify database schema is working correctly
"""
import os
import sys
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from db.database import SessionLocal
from models import ChatSession, FileEmbedding, User
from sqlalchemy import create_engine, inspect, text


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required for tests")


def test_database_connection():
    """Test basic database connection"""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_table_structure():
    """Test that all required tables exist with correct structure"""
    try:
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = [
            'users', 'auth_tokens', 'session_tokens', 'repositories', 
            'issues', 'pull_requests', 'commits', 'file_items', 
            'file_analyses', 'user_issues', 'file_embeddings', 'oauth_states',
            'chat_sessions', 'chat_messages', 'context_cards'
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"✗ Missing tables: {missing_tables}")
            return False
        
        print("✓ All required tables exist")
        return True
    except Exception as e:
        print(f"✗ Table structure check failed: {e}")
        return False

def test_file_embeddings_session_id():
    """Test that file_embeddings table has session_id column"""
    try:
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        
        # Get columns for file_embeddings table
        columns = inspector.get_columns('file_embeddings')
        column_names = [col['name'] for col in columns]
        
        if 'session_id' not in column_names:
            print("✗ file_embeddings table missing session_id column")
            print(f"Available columns: {column_names}")
            return False
        
        print("✓ file_embeddings table has session_id column")
        return True
    except Exception as e:
        print(f"✗ File embeddings column check failed: {e}")
        return False

def test_sqlalchemy_models():
    """Test that SQLAlchemy models can be used"""
    try:
        db = SessionLocal()
        
        # Test creating a user
        test_user = User(
            github_username="test_user",
            github_user_id="99999",
            email="test@example.com",
            display_name="Test User"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # Test creating a chat session
        test_session = ChatSession(
            user_id=test_user.id,
            session_id="test_session_001",
            title="Test Session",
            description="Test session for verification"
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        
        # Test creating a file embedding
        test_embedding = FileEmbedding(
            session_id=test_session.id,
            repository_id=None,
            file_path="test/file.py",
            file_name="file.py",
            file_type="python",
            chunk_text="Test file content",
            tokens=10
        )
        db.add(test_embedding)
        db.commit()
        db.refresh(test_embedding)
        
        print("✓ SQLAlchemy models working correctly")
        
        # Clean up test data
        db.delete(test_embedding)
        db.delete(test_session)
        db.delete(test_user)
        db.commit()
        
        return True
    except Exception as e:
        print(f"✗ SQLAlchemy models test failed: {e}")
        return False
    finally:
        db.close()

def test_file_deps_endpoint_query():
    """Test the specific query that was failing in the file-deps endpoint"""
    try:
        db = SessionLocal()
        
        # Create test data
        test_user = User(
            github_username="test_user_2",
            github_user_id="88888",
            email="test2@example.com",
            display_name="Test User 2"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        test_session = ChatSession(
            user_id=test_user.id,
            session_id="test_session_002",
            title="Test Session 2",
            description="Test session for file-deps endpoint"
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        
        # Test the exact query from the failing endpoint
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == test_session.id
        ).order_by(FileEmbedding.created_at.desc()).all()
        
        print(f"✓ File embeddings query successful, found {len(file_embeddings)} records")
        
        # Clean up
        db.delete(test_session)
        db.delete(test_user)
        db.commit()
        
        return True
    except Exception as e:
        print(f"✗ File-deps endpoint query test failed: {e}")
        return False
    finally:
        db.close()

def main():
    """Run all tests"""
    print("🧪 Testing YudaiV3 Database Schema...")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Table Structure", test_table_structure),
        ("File Embeddings session_id Column", test_file_embeddings_session_id),
        ("SQLAlchemy Models", test_sqlalchemy_models),
        ("File-deps Endpoint Query", test_file_deps_endpoint_query),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Database schema is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the database schema.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)