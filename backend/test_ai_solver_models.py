#!/usr/bin/env python3
"""
Test script for AI Solver models
"""
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import init_db, create_sample_data
from models import AIModel, SWEAgentConfig, AISolveSession, AISolveEdit
from sqlalchemy.orm import sessionmaker
from db.database import engine

def test_ai_solver_models():
    """Test AI solver models creation and relationships"""
    print("🧪 Testing AI Solver Models...")
    
    try:
        # Initialize database
        print("1. Initializing database...")
        init_success = init_db()
        if not init_success:
            print("❌ Database initialization failed")
            return False
        
        # Create sample data
        print("2. Creating sample data...")
        create_sample_data()
        
        # Test model queries
        print("3. Testing model queries...")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Test AI Models
            ai_models = db.query(AIModel).all()
            print(f"   ✓ Found {len(ai_models)} AI models")
            for model in ai_models:
                print(f"     - {model.name} ({model.provider}/{model.model_id})")
            
            # Test SWE-agent Configs
            swe_configs = db.query(SWEAgentConfig).all()
            print(f"   ✓ Found {len(swe_configs)} SWE-agent configs")
            for config in swe_configs:
                print(f"     - {config.name} (default: {config.is_default})")
            
            # Test Solve Sessions
            solve_sessions = db.query(AISolveSession).all()
            print(f"   ✓ Found {len(solve_sessions)} solve sessions")
            for session in solve_sessions:
                print(f"     - Session {session.id}: {session.status} (Issue {session.issue_id})")
            
            # Test Solve Edits
            solve_edits = db.query(AISolveEdit).all()
            print(f"   ✓ Found {len(solve_edits)} solve edits")
            for edit in solve_edits:
                print(f"     - {edit.edit_type}: {edit.file_path}")
            
            # Test relationships
            print("4. Testing relationships...")
            if solve_sessions:
                session = solve_sessions[0]
                print(f"   ✓ Session {session.id} has {len(session.edits)} edits")
                if session.ai_model:
                    print(f"   ✓ Session uses AI model: {session.ai_model.name}")
                if session.swe_config:
                    print(f"   ✓ Session uses SWE config: {session.swe_config.name}")
            
            print("✅ All AI Solver models tests passed!")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ai_solver_models()
    sys.exit(0 if success else 1)