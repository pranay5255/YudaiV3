"""
Integration tests for GitHub OAuth authentication

These tests verify the complete authentication flow including:
- OAuth login initiation
- OAuth callback handling
- Token management
- User authentication
- Profile management
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from models import AuthToken, User


class TestGitHubAuthIntegration:
    """Test GitHub OAuth authentication integration"""
    
    def test_auth_config_endpoint(self, test_client):
        """Test authentication configuration endpoint"""
        response = test_client.get("/auth/config")
        assert response.status_code == 200
        
        data = response.json()
        assert data["github_oauth_configured"] is True
        assert data["client_id_configured"] is True
        assert data["client_secret_configured"] is True
        assert data["redirect_uri"] == "http://localhost:3000/auth/callback"
    
    def test_auth_status_unauthenticated(self, test_client):
        """Test authentication status for unauthenticated user"""
        response = test_client.get("/auth/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["authenticated"] is False
    
    def test_auth_status_authenticated(self, test_client, auth_headers):
        """Test authentication status for authenticated user"""
        response = test_client.get("/auth/status", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["github_username"] == "testuser"
        assert data["user"]["id"] == 1
    
    def test_login_redirect(self, test_client):
        """Test OAuth login initiation"""
        response = test_client.get("/auth/login", allow_redirects=False)
        assert response.status_code == 302
        
        # Check that redirect URL contains GitHub OAuth parameters
        location = response.headers["location"]
        assert "github.com/login/oauth/authorize" in location
        assert "client_id=test_client_id" in location
        assert "scope=repo+user+email" in location
        assert "state=" in location
    
    @patch('requests.post')
    @patch('requests.get')
    def test_oauth_callback_success(self, mock_get, mock_post, test_client, mock_github_oauth_responses):
        """Test successful OAuth callback handling"""
        # Mock token exchange
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_github_oauth_responses["token_response"]
        
        # Mock user info request
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_github_oauth_responses["user_response"]
        
        # First, initiate login to get a valid state
        login_response = test_client.get("/auth/login", allow_redirects=False)
        location = login_response.headers["location"]
        
        # Extract state from the redirect URL
        state = location.split("state=")[1].split("&")[0]
        
        # Now test the callback
        response = test_client.get(f"/auth/callback?code=test_code&state={state}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Authentication successful"
        assert data["user"]["github_username"] == "testuser"
        assert data["access_token"] == "gho_test_token_123456789"
    
    def test_oauth_callback_invalid_state(self, test_client):
        """Test OAuth callback with invalid state"""
        response = test_client.get("/auth/callback?code=test_code&state=invalid_state")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is False
        assert "Invalid state parameter" in data["error"]
    
    def test_get_user_profile(self, test_client, auth_headers, dummy_user):
        """Test getting user profile"""
        response = test_client.get("/auth/profile", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["github_username"] == "testuser"
        assert data["github_user_id"] == "123456"
        assert data["email"] == "testuser@example.com"
        assert data["display_name"] == "Test User"
    
    def test_get_user_profile_unauthenticated(self, test_client):
        """Test getting user profile without authentication"""
        response = test_client.get("/auth/profile")
        assert response.status_code == 401
    
    def test_logout_success(self, test_client, auth_headers, test_db, dummy_auth_token):
        """Test successful logout"""
        # Verify token is active before logout
        assert dummy_auth_token.is_active is True
        
        response = test_client.post("/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Logged out successfully"
        
        # Verify token is deactivated after logout
        test_db.refresh(dummy_auth_token)
        assert dummy_auth_token.is_active is False
    
    def test_logout_unauthenticated(self, test_client):
        """Test logout without authentication"""
        response = test_client.post("/auth/logout")
        assert response.status_code == 401
    
    def test_expired_token_authentication(self, test_client, test_db, dummy_user):
        """Test authentication with expired token"""
        # Create an expired token
        expired_token = AuthToken(
            user_id=dummy_user.id,
            access_token="expired_token_123",
            token_type="bearer",
            scope="repo user email",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            is_active=True,
            created_at=datetime.utcnow()
        )
        test_db.add(expired_token)
        test_db.commit()
        
        headers = {"Authorization": f"Bearer {expired_token.access_token}"}
        response = test_client.get("/auth/status", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["authenticated"] is False
    
    def test_invalid_token_authentication(self, test_client):
        """Test authentication with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_123"}
        response = test_client.get("/auth/status", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["authenticated"] is False
    
    def test_multiple_active_tokens(self, test_client, test_db, dummy_user):
        """Test user with multiple active tokens"""
        # Create additional active tokens
        tokens = []
        for i in range(3):
            token = AuthToken(
                user_id=dummy_user.id,
                access_token=f"token_{i}_123456789",
                token_type="bearer",
                scope="repo user email",
                expires_at=datetime.utcnow() + timedelta(hours=8),
                is_active=True,
                created_at=datetime.utcnow()
            )
            test_db.add(token)
            tokens.append(token)
        
        test_db.commit()
        
        # Test that all tokens work
        for token in tokens:
            headers = {"Authorization": f"Bearer {token.access_token}"}
            response = test_client.get("/auth/status", headers=headers)
            assert response.status_code == 200
            
            data = response.json()
            assert data["authenticated"] is True
            assert data["user"]["github_username"] == "testuser"
    
    @patch('requests.post')
    @patch('requests.get')
    def test_user_update_on_login(self, mock_get, mock_post, test_client, test_db, dummy_user, mock_github_oauth_responses):
        """Test that user information is updated on subsequent logins"""
        # Mock token exchange
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_github_oauth_responses["token_response"]
        
        # Mock updated user info
        updated_user_response = mock_github_oauth_responses["user_response"].copy()
        updated_user_response["name"] = "Updated Test User"
        updated_user_response["email"] = "updated@example.com"
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = updated_user_response
        
        # Store original user data
        original_name = dummy_user.display_name
        original_email = dummy_user.email
        
        # Initiate login to get state
        login_response = test_client.get("/auth/login", allow_redirects=False)
        location = login_response.headers["location"]
        state = location.split("state=")[1].split("&")[0]
        
        # Complete OAuth callback
        response = test_client.get(f"/auth/callback?code=test_code&state={state}")
        assert response.status_code == 200
        
        # Verify user information was updated
        test_db.refresh(dummy_user)
        assert dummy_user.display_name == "Updated Test User"
        assert dummy_user.email == "updated@example.com"
        assert dummy_user.display_name != original_name
        assert dummy_user.email != original_email


class TestTokenManagement:
    """Test token management functionality"""
    
    def test_token_creation(self, test_db, dummy_user):
        """Test creating a new auth token"""
        token = AuthToken(
            user_id=dummy_user.id,
            access_token="new_token_123456789",
            token_type="bearer",
            scope="repo user email",
            expires_at=datetime.utcnow() + timedelta(hours=8),
            is_active=True
        )
        test_db.add(token)
        test_db.commit()
        test_db.refresh(token)
        
        assert token.id is not None
        assert token.user_id == dummy_user.id
        assert token.access_token == "new_token_123456789"
        assert token.is_active is True
    
    def test_token_deactivation(self, test_db, dummy_auth_token):
        """Test deactivating an auth token"""
        assert dummy_auth_token.is_active is True
        
        dummy_auth_token.is_active = False
        test_db.commit()
        test_db.refresh(dummy_auth_token)
        
        assert dummy_auth_token.is_active is False
    
    def test_token_expiration_check(self, test_db, dummy_user):
        """Test token expiration logic"""
        # Create expired token
        expired_token = AuthToken(
            user_id=dummy_user.id,
            access_token="expired_token_123",
            token_type="bearer",
            scope="repo user email",
            expires_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True
        )
        test_db.add(expired_token)
        test_db.commit()
        
        # Query for active, non-expired tokens
        active_tokens = test_db.query(AuthToken).filter(
            AuthToken.user_id == dummy_user.id,
            AuthToken.is_active,
            AuthToken.expires_at > datetime.utcnow()
        ).all()
        
        # Should not include the expired token
        assert len(active_tokens) == 0
        
        # But should include valid tokens
        valid_token = AuthToken(
            user_id=dummy_user.id,
            access_token="valid_token_123",
            token_type="bearer",
            scope="repo user email",
            expires_at=datetime.utcnow() + timedelta(hours=8),
            is_active=True
        )
        test_db.add(valid_token)
        test_db.commit()
        
        active_tokens = test_db.query(AuthToken).filter(
            AuthToken.user_id == dummy_user.id,
            AuthToken.is_active,
            AuthToken.expires_at > datetime.utcnow()
        ).all()
        
        assert len(active_tokens) == 1
        assert active_tokens[0].access_token == "valid_token_123"


class TestUserManagement:
    """Test user management functionality"""
    
    def test_user_creation(self, test_db):
        """Test creating a new user"""
        user = User(
            github_username="newuser",
            github_user_id="789012",
            email="newuser@example.com",
            display_name="New User",
            avatar_url="https://avatars.githubusercontent.com/u/789012?v=4"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.id is not None
        assert user.github_username == "newuser"
        assert user.github_user_id == "789012"
        assert user.email == "newuser@example.com"
    
    def test_user_uniqueness(self, test_db, dummy_user):
        """Test that GitHub user ID must be unique"""
        # Try to create another user with the same GitHub ID
        duplicate_user = User(
            github_username="different_username",
            github_user_id="123456",  # Same as dummy_user
            email="different@example.com"
        )
        test_db.add(duplicate_user)
        
        # This should raise an integrity error
        with pytest.raises(Exception):
            test_db.commit()
    
    def test_user_relationships(self, test_db, dummy_user, dummy_auth_token, dummy_repository):
        """Test user relationships with tokens and repositories"""
        # Test user -> tokens relationship
        assert len(dummy_user.auth_tokens) == 1
        assert dummy_user.auth_tokens[0].access_token == "gho_test_token_123456789"
        
        # Test user -> repositories relationship
        assert len(dummy_user.repositories) == 1
        assert dummy_user.repositories[0].repo_name == "test-repo"
        
        # Test token -> user relationship
        assert dummy_auth_token.user.github_username == "testuser"
        
        # Test repository -> user relationship
        assert dummy_repository.user.github_username == "testuser" 