#!/usr/bin/env python3
"""
Test script for AI Solver Core functionality
Tests the solver adapter with deterministic stub of SWE-agent
"""
import sys
import os
import asyncio
import tempfile
import json
from datetime import datetime, timedelta

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import init_db, SessionLocal
from models import User, Repository, Issue, AIModel, SWEAgentConfig
from solver.ai_solver import AISolverAdapter
from schemas.ai_solver import SolveStatus


class MockSWEAgent:
    """Mock SWE-agent for testing purposes"""
    
    @staticmethod
    def create_mock_trajectory():
        """Create a deterministic mock trajectory"""
        return {
            "steps": [
                {
                    "step_index": 1,
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": {
                        "command": "explore_repository",
                        "args": {"path": "."}
                    },
                    "result": "Repository explored successfully"
                },
                {
                    "step_index": 2,
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": {
                        "command": "str_replace_editor",
                        "args": {
                            "path": "src/auth.py",
                            "old_str": "# TODO: Implement authentication",
                            "new_str": "def authenticate_user(username, password):\n    # Basic authentication implementation\n    return username == 'admin' and password == 'secret'"
                        }
                    },
                    "result": "File edited successfully"
                },
                {
                    "step_index": 3,
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": {
                        "command": "create_file",
                        "args": {
                            "path": "tests/test_auth.py",
                            "file_text": "import unittest\nfrom src.auth import authenticate_user\n\nclass TestAuth(unittest.TestCase):\n    def test_authentication(self):\n        self.assertTrue(authenticate_user('admin', 'secret'))\n        self.assertFalse(authenticate_user('user', 'wrong'))"
                        }
                    },
                    "result": "Test file created successfully"
                }
            ],
            "final_state": "completed",
            "total_steps": 3,
            "session_id": "mock_session"
        }


async def test_solver_core():
    """Test the AI Solver core functionality"""
    print("🧪 Testing AI Solver Core...")
    
    try:
        # Initialize database
        print("1. Initializing database...")
        init_success = init_db()
        if not init_success:
            print("❌ Database initialization failed")
            return False
        
        # Create test data
        print("2. Creating test data...")
        db = SessionLocal()
        
        try:
            # Create test user
            test_user = User(
                github_username="test_solver_user",
                github_user_id="99999",
                email="test@solver.com",
                display_name="Test Solver User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            
            # Create test repository
            test_repo = Repository(
                user_id=test_user.id,
                github_repo_id=999999,
                name="test-solver-repo",
                owner="test_solver_user",
                full_name="test_solver_user/test-solver-repo",
                html_url="https://github.com/test_solver_user/test-solver-repo",
                clone_url="https://github.com/test_solver_user/test-solver-repo.git",
                language="Python"
            )
            db.add(test_repo)
            db.commit()
            db.refresh(test_repo)
            
            # Create test issue
            test_issue = Issue(
                github_issue_id=99999,
                repository_id=test_repo.id,
                number=1,
                title="Implement user authentication",
                body="We need to add basic user authentication functionality to the application. Please implement a simple username/password authentication system.",
                state="open",
                html_url="https://github.com/test_solver_user/test-solver-repo/issues/1",
                author_username="test_solver_user",
                github_created_at=datetime.utcnow(),
                github_updated_at=datetime.utcnow()
            )
            db.add(test_issue)
            db.commit()
            db.refresh(test_issue)
            
            # Create test AI model
            test_ai_model = AIModel(
                name="Test Claude",
                provider="openrouter",
                model_id="anthropic/claude-3.5-sonnet",
                config={"temperature": 0.1, "max_tokens": 4000},
                is_active=True
            )
            db.add(test_ai_model)
            db.commit()
            db.refresh(test_ai_model)
            
            # Create test SWE config
            test_swe_config = SWEAgentConfig(
                name="Test Config",
                config_path="/app/solver/config.yaml",
                parameters={"max_iterations": 10, "max_time_seconds": 300},
                is_default=True
            )
            db.add(test_swe_config)
            db.commit()
            db.refresh(test_swe_config)
            
            print(f"   ✓ Created test user: {test_user.github_username}")
            print(f"   ✓ Created test repository: {test_repo.full_name}")
            print(f"   ✓ Created test issue: {test_issue.title}")
            print(f"   ✓ Created test AI model: {test_ai_model.name}")
            print(f"   ✓ Created test SWE config: {test_swe_config.name}")
            
            # Test solver adapter initialization
            print("3. Testing solver adapter...")
            solver = AISolverAdapter(db)
            print("   ✓ Solver adapter initialized")
            
            # Test session status (should return None for non-existent session)
            print("4. Testing session status...")
            status = solver.get_session_status(99999)
            if status is None:
                print("   ✓ Non-existent session returns None")
            else:
                print("   ❌ Non-existent session should return None")
                return False
            
            # Mock the SWE-agent execution for testing
            print("5. Testing solver workflow (mocked)...")
            
            # Create a mock solver that doesn't actually run SWE-agent
            class MockAISolverAdapter(AISolverAdapter):
                async def _execute_sweagent(self, session_id, repo_url, issue_title, issue_body, branch, ai_model_id=None, swe_config_id=None):
                    """Mock SWE-agent execution"""
                    print(f"   🔧 Mock SWE-agent execution for session {session_id}")
                    print(f"      Repository: {repo_url}")
                    print(f"      Issue: {issue_title}")
                    print(f"      Branch: {branch}")
                    
                    # Simulate some processing time
                    await asyncio.sleep(0.1)
                    
                    # Return mock trajectory
                    return MockSWEAgent.create_mock_trajectory()
            
            # Use mock solver
            mock_solver = MockAISolverAdapter(db)
            
            # Run solver
            session_id = await mock_solver.run_solver(
                issue_id=test_issue.id,
                user_id=test_user.id,
                repo_url=test_repo.clone_url,
                branch="main",
                ai_model_id=test_ai_model.id,
                swe_config_id=test_swe_config.id
            )
            
            print(f"   ✓ Solver completed with session ID: {session_id}")
            
            # Test session status after completion
            print("6. Testing session status after completion...")
            status = mock_solver.get_session_status(session_id)
            if status:
                print(f"   ✓ Session status: {status['status']}")
                print(f"   ✓ Total edits: {status['total_edits']}")
                print(f"   ✓ Files modified: {status['files_modified']}")
                print(f"   ✓ Trajectory steps: {status['trajectory_steps']}")
                
                if status['status'] == SolveStatus.COMPLETED:
                    print("   ✓ Session completed successfully")
                else:
                    print(f"   ❌ Expected COMPLETED status, got {status['status']}")
                    return False
            else:
                print("   ❌ Session status should not be None")
                return False
            
            # Test cancellation (should fail for completed session)
            print("7. Testing session cancellation...")
            cancelled = await mock_solver.cancel_session(session_id, test_user.id)
            if not cancelled:
                print("   ✓ Cannot cancel completed session (expected)")
            else:
                print("   ❌ Should not be able to cancel completed session")
                return False
            
            print("✅ All AI Solver core tests passed!")
            return True
            
        finally:
            # Cleanup test data
            db.query(Issue).filter(Issue.github_issue_id == 99999).delete()
            db.query(Repository).filter(Repository.github_repo_id == 999999).delete()
            db.query(User).filter(User.github_username == "test_solver_user").delete()
            db.query(AIModel).filter(AIModel.name == "Test Claude").delete()
            db.query(SWEAgentConfig).filter(SWEAgentConfig.name == "Test Config").delete()
            db.commit()
            db.close()
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_solver_core())
    sys.exit(0 if success else 1)