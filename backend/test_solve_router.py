"""
Test suite for AI Solver Router
Tests all endpoints and authentication functionality
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta

# Import the main app and dependencies
from run_server import app
from db.database import get_db, Base
from models import User, Issue, Repository, AISolveSession, SessionToken
from auth.auth_utils import get_current_user
from schemas.ai_solver import SolveStatus

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_solve_router.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test database tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_get_current_user():
    """Override auth dependency for testing - returns a mock user"""
    return User(
        id=1,
        github_id=12345,
        github_username="testuser",
        email="test@example.com",
        avatar_url="https://example.com/avatar.jpg"
    )

# Override dependencies
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

class TestSolveRouter:
    """Test cases for the AI Solver Router"""
    
    def setup_method(self):
        """Set up test data before each test"""
        self.db = TestingSessionLocal()
        
        # Create test user
        self.test_user = User(
            id=1,
            github_id=12345,
            github_username="testuser",
            email="test@example.com",
            avatar_url="https://example.com/avatar.jpg"
        )
        self.db.add(self.test_user)
        
        # Create test repository
        self.test_repo = Repository(
            id=1,
            name="test-repo",
            full_name="testuser/test-repo",
            html_url="https://github.com/testuser/test-repo",
            clone_url="https://github.com/testuser/test-repo.git",
            owner_id=1
        )
        self.db.add(self.test_repo)
        
        # Create test issue
        self.test_issue = Issue(
            id=1,
            title="Test Issue",
            body="This is a test issue",
            number=1,
            state="open",
            repository_id=1,
            author_id=1
        )
        self.db.add(self.test_issue)
        
        self.db.commit()
    
    def teardown_method(self):
        """Clean up after each test"""
        self.db.query(AISolveSession).delete()
        self.db.query(Issue).delete()
        self.db.query(Repository).delete()
        self.db.query(User).delete()
        self.db.commit()
        self.db.close()
    
    @patch('solver.ai_solver.AISolverAdapter.run_solver')
    def test_start_solve_session_success(self, mock_run_solver):
        """Test successful solve session start"""
        mock_run_solver.return_value = AsyncMock()
        
        response = client.post(
            "/api/v1/issues/1/solve",
            json={
                "repo_url": "https://github.com/testuser/test-repo.git",
                "branch_name": "main",
                "ai_model_id": None,
                "swe_config_id": None
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI Solver started successfully"
        assert data["issue_id"] == 1
        assert data["status"] == "started"
        assert "session_id" in data
    
    def test_start_solve_session_issue_not_found(self):
        """Test solve session start with non-existent issue"""
        response = client.post(
            "/api/v1/issues/999/solve",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
        assert "Issue not found" in response.json()["detail"]
    
    def test_start_solve_session_no_auth(self):
        """Test solve session start without authentication"""
        response = client.post("/api/v1/issues/1/solve")
        
        assert response.status_code == 401
        assert "Authorization header required" in response.json()["detail"]
    
    def test_get_solve_session_success(self):
        """Test successful solve session retrieval"""
        # Create a test session
        session = AISolveSession(
            id=1,
            user_id=1,
            issue_id=1,
            status=SolveStatus.RUNNING,
            repo_url="https://github.com/testuser/test-repo.git",
            branch_name="main"
        )
        self.db.add(session)
        self.db.commit()
        
        response = client.get(
            "/api/v1/solve-sessions/1",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["user_id"] == 1
        assert data["issue_id"] == 1
        assert data["status"] == "running"
    
    def test_get_solve_session_not_found(self):
        """Test solve session retrieval with non-existent session"""
        response = client.get(
            "/api/v1/solve-sessions/999",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 404
        assert "Solve session not found" in response.json()["detail"]
    
    @patch('solver.ai_solver.AISolverAdapter.get_session_status')
    def test_get_solve_session_stats_success(self, mock_get_stats):
        """Test successful solve session stats retrieval"""
        # Create a test session
        session = AISolveSession(
            id=1,
            user_id=1,
            issue_id=1,
            status=SolveStatus.COMPLETED,
            repo_url="https://github.com/testuser/test-repo.git",
            branch_name="main"
        )
        self.db.add(session)
        self.db.commit()
        
        # Mock stats response
        mock_get_stats.return_value = {
            "session_id": 1,
            "status": "completed",
            "total_edits": 5,
            "files_modified": 3,
            "lines_added": 50,
            "lines_removed": 10,
            "duration_seconds": 300,
            "last_activity": datetime.utcnow().isoformat(),
            "trajectory_steps": 15
        }
        
        response = client.get(
            "/api/v1/solve-sessions/1/stats",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == 1
        assert data["status"] == "completed"
        assert data["total_edits"] == 5
        assert data["files_modified"] == 3
    
    @patch('solver.ai_solver.AISolverAdapter.cancel_session')
    def test_cancel_solve_session_success(self, mock_cancel):
        """Test successful solve session cancellation"""
        # Create a test session
        session = AISolveSession(
            id=1,
            user_id=1,
            issue_id=1,
            status=SolveStatus.RUNNING,
            repo_url="https://github.com/testuser/test-repo.git",
            branch_name="main"
        )
        self.db.add(session)
        self.db.commit()
        
        mock_cancel.return_value = True
        
        response = client.post(
            "/api/v1/solve-sessions/1/cancel",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Solve session cancelled successfully"
        assert data["session_id"] == 1
        assert data["status"] == "cancelled"
    
    @patch('solver.ai_solver.AISolverAdapter.cancel_session')
    def test_cancel_solve_session_failed(self, mock_cancel):
        """Test failed solve session cancellation"""
        # Create a test session
        session = AISolveSession(
            id=1,
            user_id=1,
            issue_id=1,
            status=SolveStatus.COMPLETED,  # Cannot cancel completed session
            repo_url="https://github.com/testuser/test-repo.git",
            branch_name="main"
        )
        self.db.add(session)
        self.db.commit()
        
        mock_cancel.return_value = False
        
        response = client.post(
            "/api/v1/solve-sessions/1/cancel",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "Cannot cancel session with status" in response.json()["detail"]
    
    def test_list_user_solve_sessions_success(self):
        """Test successful user solve sessions listing"""
        # Create test sessions
        for i in range(3):
            session = AISolveSession(
                id=i+1,
                user_id=1,
                issue_id=1,
                status=SolveStatus.COMPLETED if i % 2 == 0 else SolveStatus.RUNNING,
                repo_url="https://github.com/testuser/test-repo.git",
                branch_name="main"
            )
            self.db.add(session)
        self.db.commit()
        
        response = client.get(
            "/api/v1/solve-sessions",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(session["user_id"] == 1 for session in data)
    
    def test_list_user_solve_sessions_with_status_filter(self):
        """Test user solve sessions listing with status filter"""
        # Create test sessions with different statuses
        statuses = [SolveStatus.COMPLETED, SolveStatus.RUNNING, SolveStatus.FAILED]
        for i, status in enumerate(statuses):
            session = AISolveSession(
                id=i+1,
                user_id=1,
                issue_id=1,
                status=status,
                repo_url="https://github.com/testuser/test-repo.git",
                branch_name="main"
            )
            self.db.add(session)
        self.db.commit()
        
        response = client.get(
            "/api/v1/solve-sessions?status=completed",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"
    
    def test_list_user_solve_sessions_invalid_status(self):
        """Test user solve sessions listing with invalid status filter"""
        response = client.get(
            "/api/v1/solve-sessions?status=invalid_status",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]
    
    def test_solver_health_check(self):
        """Test solver health check endpoint"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-solver"
        assert data["version"] == "1.0.0"
        assert "checks" in data
        assert "database" in data["checks"]
        assert "swe_agent" in data["checks"]
        assert "docker" in data["checks"]
        assert "storage" in data["checks"]


class TestAuthValidation:
    """Test cases for authentication and payment validation"""
    
    def test_validate_auth_payment_always_true(self):
        """Test that auth validation always returns True as requested"""
        from routers.solve_router import validate_auth_payment
        
        # Mock user
        mock_user = User(
            id=1,
            github_id=12345,
            github_username="testuser",
            email="test@example.com"
        )
        
        # Should always return True
        result = validate_auth_payment(mock_user)
        assert result is True
    
    def test_auth_validation_has_comprehensive_todos(self):
        """Test that auth validation function has comprehensive TODO comments"""
        import inspect
        from routers.solve_router import validate_auth_payment
        
        source = inspect.getsource(validate_auth_payment)
        
        # Check for key TODO items
        assert "TODO: Implement proper authentication" in source
        assert "subscription status" in source
        assert "payment method" in source
        assert "usage limits" in source
        assert "rate limits" in source
        assert "fraud detection" in source
        assert "audit logging" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])