"""
Pytest configuration and fixtures for YudaiV3 backend tests

This module provides shared fixtures for database setup, test client,
and dummy data for integration tests.
"""

import pytest
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the main FastAPI app
from repo_processor.filedeps import app

# Import database and models
from db.database import get_db
from models import Base, User, AuthToken, Repository, FileItem

# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Create a new session for each test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up all tables for next test
        for table in reversed(Base.metadata.sorted_tables):
            test_engine.execute(table.delete())

@pytest.fixture(scope="function")
def test_client(test_db):
    """Create a test client with dependency override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.fixture
def dummy_user(test_db):
    """Create a dummy user for testing"""
    user = User(
        github_username="testuser",
        github_user_id="123456",
        email="testuser@example.com",
        display_name="Test User",
        avatar_url="https://avatars.githubusercontent.com/u/123456?v=4",
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user

@pytest.fixture
def dummy_auth_token(test_db, dummy_user):
    """Create a dummy auth token for testing"""
    token = AuthToken(
        user_id=dummy_user.id,
        access_token="gho_test_token_123456789",
        token_type="bearer",
        scope="repo user email",
        expires_at=datetime.utcnow() + timedelta(hours=8),
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(token)
    test_db.commit()
    test_db.refresh(token)
    return token

@pytest.fixture
def dummy_repository(test_db, dummy_user):
    """Create a dummy repository for testing"""
    repo = Repository(
        user_id=dummy_user.id,
        repo_url="https://github.com/testuser/test-repo",
        repo_name="test-repo",
        repo_owner="testuser",
        total_files=10,
        total_tokens=5000,
        raw_data={"test": "data"},
        processed_data={"processed": "data"},
        status="completed",
        created_at=datetime.utcnow(),
        processed_at=datetime.utcnow()
    )
    test_db.add(repo)
    test_db.commit()
    test_db.refresh(repo)
    return repo

@pytest.fixture
def dummy_file_items(test_db, dummy_repository):
    """Create dummy file items for testing"""
    files = [
        FileItem(
            repository_id=dummy_repository.id,
            name="main.py",
            path="src/main.py",
            file_type="INTERNAL",
            category="Source Code",
            tokens=1000,
            is_directory=False,
            content_size=4000,
            created_at=datetime.utcnow()
        ),
        FileItem(
            repository_id=dummy_repository.id,
            name="test.py",
            path="tests/test.py",
            file_type="INTERNAL",
            category="Test Code",
            tokens=500,
            is_directory=False,
            content_size=2000,
            created_at=datetime.utcnow()
        ),
        FileItem(
            repository_id=dummy_repository.id,
            name="src",
            path="src",
            file_type="INTERNAL",
            category="Directory",
            tokens=0,
            is_directory=True,
            content_size=0,
            created_at=datetime.utcnow()
        )
    ]
    
    for file_item in files:
        test_db.add(file_item)
    
    test_db.commit()
    
    for file_item in files:
        test_db.refresh(file_item)
    
    return files

@pytest.fixture
def auth_headers(dummy_auth_token):
    """Create authorization headers for testing"""
    return {"Authorization": f"Bearer {dummy_auth_token.access_token}"}

@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses for testing"""
    mock_api = MagicMock()
    
    # Mock user repositories
    mock_api.repos.list_for_authenticated_user.return_value = [
        {
            "id": 123456,
            "name": "test-repo",
            "full_name": "testuser/test-repo",
            "description": "A test repository",
            "private": False,
            "html_url": "https://github.com/testuser/test-repo",
            "clone_url": "https://github.com/testuser/test-repo.git",
            "updated_at": "2023-01-01T00:00:00Z",
            "language": "Python",
            "stargazers_count": 10,
            "forks_count": 5
        }
    ]
    
    # Mock repository details
    mock_api.repos.get.return_value = {
        "id": 123456,
        "name": "test-repo",
        "full_name": "testuser/test-repo",
        "description": "A test repository",
        "private": False,
        "html_url": "https://github.com/testuser/test-repo",
        "clone_url": "https://github.com/testuser/test-repo.git",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "pushed_at": "2023-01-01T00:00:00Z",
        "language": "Python",
        "stargazers_count": 10,
        "forks_count": 5,
        "open_issues_count": 2,
        "size": 1024,
        "default_branch": "main",
        "license": {"key": "mit", "name": "MIT License"},
        "archived": False,
        "disabled": False
    }
    
    # Mock repository languages
    mock_api.repos.list_languages.return_value = {
        "Python": 8000,
        "JavaScript": 2000
    }
    
    # Mock repository topics
    mock_api.repos.list_all_topics_for_repository.return_value = {
        "names": ["python", "api", "test"]
    }
    
    # Mock issues
    mock_api.issues.list_for_repo.return_value = [
        {
            "id": 1,
            "number": 1,
            "title": "Test Issue",
            "body": "This is a test issue",
            "state": "open",
            "html_url": "https://github.com/testuser/test-repo/issues/1",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "closed_at": None,
            "labels": [],
            "assignees": [],
            "user": {"login": "testuser", "id": 123456}
        }
    ]
    
    # Mock issue creation
    mock_api.issues.create.return_value = {
        "id": 2,
        "number": 2,
        "title": "New Test Issue",
        "body": "This is a new test issue",
        "state": "open",
        "html_url": "https://github.com/testuser/test-repo/issues/2",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "labels": [],
        "assignees": [],
        "user": {"login": "testuser", "id": 123456}
    }
    
    # Mock pull requests
    mock_api.pulls.list.return_value = [
        {
            "id": 1,
            "number": 1,
            "title": "Test PR",
            "body": "This is a test PR",
            "state": "open",
            "html_url": "https://github.com/testuser/test-repo/pull/1",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "labels": [],
            "assignees": [],
            "user": {"login": "testuser", "id": 123456},
            "head": {"ref": "feature-branch", "sha": "abc123"},
            "base": {"ref": "main", "sha": "def456"}
        }
    ]
    
    # Mock commits
    mock_api.repos.list_commits.return_value = [
        {
            "sha": "abc123",
            "commit": {
                "message": "Test commit",
                "author": {"name": "Test User", "email": "test@example.com", "date": "2023-01-01T00:00:00Z"},
                "committer": {"name": "Test User", "email": "test@example.com", "date": "2023-01-01T00:00:00Z"}
            },
            "html_url": "https://github.com/testuser/test-repo/commit/abc123",
            "parents": [{"sha": "def456"}]
        }
    ]
    
    # Mock repository search
    mock_api.search.repos.return_value = {
        "total_count": 1,
        "incomplete_results": False,
        "items": [
            {
                "id": 123456,
                "name": "test-repo",
                "full_name": "testuser/test-repo",
                "description": "A test repository",
                "private": False,
                "html_url": "https://github.com/testuser/test-repo",
                "clone_url": "https://github.com/testuser/test-repo.git",
                "updated_at": "2023-01-01T00:00:00Z",
                "language": "Python",
                "stargazers_count": 10,
                "forks_count": 5,
                "score": 1.0
            }
        ]
    }
    
    return mock_api

@pytest.fixture
def mock_github_oauth_responses():
    """Mock GitHub OAuth API responses"""
    return {
        "token_response": {
            "access_token": "gho_test_token_123456789",
            "token_type": "bearer",
            "scope": "repo,user,email"
        },
        "user_response": {
            "id": 123456,
            "login": "testuser",
            "name": "Test User",
            "email": "testuser@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/123456?v=4"
        }
    }

@pytest.fixture
def mock_daifu_response():
    """Mock DAifu chat API response"""
    return {
        "choices": [
            {
                "message": {
                    "content": "Hello! I'm DAifu, your AI assistant. How can I help you with your GitHub repository today?"
                }
            }
        ]
    }

# Environment variable fixtures for testing
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    test_env = {
        "GITHUB_CLIENT_ID": "test_client_id",
        "GITHUB_CLIENT_SECRET": "test_client_secret",
        "GITHUB_REDIRECT_URI": "http://localhost:3000/auth/callback",
        "OPENROUTER_API_KEY": "test_openrouter_key",
        "DATABASE_URL": TEST_DATABASE_URL
    }
    
    with patch.dict(os.environ, test_env):
        yield 