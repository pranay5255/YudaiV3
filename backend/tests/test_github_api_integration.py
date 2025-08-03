"""
Integration tests for GitHub API functionality

These tests verify the complete GitHub API integration including:
- Repository management
- Issue creation and listing
- Pull request management
- Commit history
- Repository search
- Authentication integration
"""

from unittest.mock import MagicMock, patch

import pytest
from auth.github_oauth import get_github_api


class TestGitHubAPIIntegration:
    """Test GitHub API integration with authentication"""
    
    def test_get_user_repositories(self, test_client, auth_headers, mock_github_api):
        """Test getting user's repositories"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "test-repo"
            assert data[0]["full_name"] == "testuser/test-repo"
            assert data[0]["private"] is False
            assert data[0]["language"] == "Python"
    
    def test_get_user_repositories_unauthenticated(self, test_client):
        """Test getting repositories without authentication"""
        response = test_client.get("/github/repositories")
        assert response.status_code == 401
    
    def test_get_repository_details(self, test_client, auth_headers, mock_github_api):
        """Test getting detailed repository information"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert data["name"] == "test-repo"
            assert data["full_name"] == "testuser/test-repo"
            assert data["language"] == "Python"
            assert data["languages"] == {"Python": 8000, "JavaScript": 2000}
            assert data["topics"] == ["python", "api", "test"]
            assert data["default_branch"] == "main"
    
    def test_get_repository_issues(self, test_client, auth_headers, mock_github_api):
        """Test getting repository issues"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo/issues", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            assert data[0]["number"] == 1
            assert data[0]["title"] == "Test Issue"
            assert data[0]["state"] == "open"
            assert data[0]["user"]["login"] == "testuser"
    
    def test_get_repository_issues_with_state(self, test_client, auth_headers, mock_github_api):
        """Test getting repository issues with specific state"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo/issues?state=closed", headers=auth_headers)
            assert response.status_code == 200
            
            # Verify that the state parameter was passed to the API
            mock_github_api.issues.list_for_repo.assert_called_with(
                owner="testuser",
                repo="test-repo",
                state="closed",
                per_page=100
            )
    
    def test_create_repository_issue(self, test_client, auth_headers, mock_github_api):
        """Test creating a new repository issue"""
        issue_data = {
            "title": "New Test Issue",
            "body": "This is a new test issue",
            "labels": ["bug", "enhancement"],
            "assignees": ["testuser"]
        }
        
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.post(
                "/github/repositories/testuser/test-repo/issues",
                json=issue_data,
                headers=auth_headers
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["number"] == 2
            assert data["title"] == "New Test Issue"
            assert data["state"] == "open"
            
            # Verify the API was called with correct parameters
            mock_github_api.issues.create.assert_called_once_with(
                owner="testuser",
                repo="test-repo",
                title="New Test Issue",
                body="This is a new test issue",
                labels=["bug", "enhancement"],
                assignees=["testuser"]
            )
    
    def test_get_repository_pulls(self, test_client, auth_headers, mock_github_api):
        """Test getting repository pull requests"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo/pulls", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            assert data[0]["number"] == 1
            assert data[0]["title"] == "Test PR"
            assert data[0]["state"] == "open"
            assert data[0]["head"]["ref"] == "feature-branch"
            assert data[0]["base"]["ref"] == "main"
    
    def test_get_repository_commits(self, test_client, auth_headers, mock_github_api):
        """Test getting repository commits"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo/commits", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 1
            assert data[0]["sha"] == "abc123"
            assert data[0]["message"] == "Test commit"
            assert data[0]["author"]["name"] == "Test User"
    
    def test_get_repository_commits_with_branch(self, test_client, auth_headers, mock_github_api):
        """Test getting repository commits for specific branch"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/testuser/test-repo/commits?branch=develop", headers=auth_headers)
            assert response.status_code == 200
            
            # Verify the branch parameter was passed to the API
            mock_github_api.repos.list_commits.assert_called_with(
                owner="testuser",
                repo="test-repo",
                sha="develop",
                per_page=100
            )
    
    def test_search_repositories(self, test_client, auth_headers, mock_github_api):
        """Test searching repositories"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/search/repositories?q=python", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert data["total_count"] == 1
            assert data["incomplete_results"] is False
            assert len(data["items"]) == 1
            assert data["items"][0]["name"] == "test-repo"
            assert data["items"][0]["score"] == 1.0
    
    def test_search_repositories_with_params(self, test_client, auth_headers, mock_github_api):
        """Test searching repositories with sort and order parameters"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get(
                "/github/search/repositories?q=python&sort=forks&order=asc",
                headers=auth_headers
            )
            assert response.status_code == 200
            
            # Verify the parameters were passed to the API
            mock_github_api.search.repos.assert_called_with(
                q="python",
                sort="forks",
                order="asc",
                per_page=30
            )


class TestGitHubAPIAuthentication:
    """Test GitHub API authentication and token handling"""
    
    def test_github_api_instance_creation(self, test_db, dummy_user, dummy_auth_token):
        """Test creating GitHub API instance for authenticated user"""
        api = get_github_api(dummy_user.id, test_db)
        assert api is not None
        # Note: We can't easily test the token without mocking GhApi
    
    def test_github_api_no_valid_token(self, test_db, dummy_user):
        """Test GitHub API instance creation with no valid token"""
        with pytest.raises(Exception) as exc_info:
            get_github_api(dummy_user.id, test_db)
        
        assert "No valid GitHub token found" in str(exc_info.value)
    
    def test_github_api_expired_token(self, test_db, dummy_user):
        """Test GitHub API instance creation with expired token"""
        from datetime import datetime, timedelta

        from models import AuthToken
        
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
        
        with pytest.raises(Exception) as exc_info:
            get_github_api(dummy_user.id, test_db)
        
        assert "No valid GitHub token found" in str(exc_info.value)


class TestGitHubAPIErrorHandling:
    """Test GitHub API error handling"""
    
    def test_github_api_error_handling(self, test_client, auth_headers):
        """Test GitHub API error handling"""
        mock_api = MagicMock()
        mock_api.repos.list_for_authenticated_user.side_effect = Exception("GitHub API Error")
        
        with patch('github.github_api.get_github_api', return_value=mock_api):
            response = test_client.get("/github/repositories", headers=auth_headers)
            assert response.status_code == 400
            
            data = response.json()
            assert "Failed to fetch repositories" in data["detail"]
    
    def test_repository_not_found_error(self, test_client, auth_headers):
        """Test repository not found error handling"""
        mock_api = MagicMock()
        mock_api.repos.get.side_effect = Exception("Repository not found")
        
        with patch('github.github_api.get_github_api', return_value=mock_api):
            response = test_client.get("/github/repositories/testuser/nonexistent-repo", headers=auth_headers)
            assert response.status_code == 400
            
            data = response.json()
            assert "Failed to fetch repository details" in data["detail"]
    
    def test_issue_creation_error(self, test_client, auth_headers):
        """Test issue creation error handling"""
        mock_api = MagicMock()
        mock_api.issues.create.side_effect = Exception("Permission denied")
        
        issue_data = {
            "title": "Test Issue",
            "body": "Test body"
        }
        
        with patch('github.github_api.get_github_api', return_value=mock_api):
            response = test_client.post(
                "/github/repositories/testuser/test-repo/issues",
                json=issue_data,
                headers=auth_headers
            )
            assert response.status_code == 400
            
            data = response.json()
            assert "Failed to create issue" in data["detail"]


class TestRepositoryDataIntegration:
    """Test integration between GitHub API and repository data storage"""
    
    def test_repository_extraction_with_auth(self, test_client, auth_headers, dummy_user):
        """Test repository extraction with authenticated user"""
        repo_data = {
            "repo_url": "https://github.com/testuser/test-repo",
            "max_file_size": 1000000
        }
        
        # Mock the GitIngest extraction
        with patch('repo_processor.scraper_script.extract_repository_data') as mock_extract:
            mock_extract.return_value = {
                "extraction_info": {
                    "source_url": "https://github.com/testuser/test-repo"
                },
                "raw_response": {
                    "tree": "├── src/\n│   └── main.py\n└── README.md",
                    "content": "# Test Repository"
                }
            }
            
            response = test_client.post("/extract", json=repo_data, headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert data["name"] == "test-repo"
            assert data["type"] == "INTERNAL"
            assert data["isDirectory"] is True
    
    def test_repository_listing_with_auth(self, test_client, auth_headers, dummy_repository):
        """Test repository listing for authenticated user"""
        response = test_client.get("/repositories", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["repo_name"] == "test-repo"
        assert data[0]["repo_owner"] == "testuser"
        assert data[0]["total_files"] == 10
        assert data[0]["total_tokens"] == 5000
    
    def test_repository_files_listing(self, test_client, auth_headers, dummy_repository, dummy_file_items):
        """Test repository files listing"""
        response = test_client.get(f"/repositories/{dummy_repository.id}/files", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 3
        
        # Check file items
        file_names = [item["name"] for item in data]
        assert "main.py" in file_names
        assert "test.py" in file_names
        assert "src" in file_names
        
        # Check directory flag
        src_dir = next(item for item in data if item["name"] == "src")
        assert src_dir["is_directory"] is True
        
        main_file = next(item for item in data if item["name"] == "main.py")
        assert main_file["is_directory"] is False
        assert main_file["tokens"] == 1000

    def test_get_repository_by_url(self, test_client, auth_headers, dummy_repository):
        """Repository can be retrieved by exact URL"""
        response = test_client.get(
            "/repositories",
            params={"repo_url": dummy_repository.repo_url},
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["repo_url"] == dummy_repository.repo_url
        assert data["repo_name"] == dummy_repository.repo_name

    def test_get_repository_by_url_not_found(self, test_client, auth_headers):
        """404 returned when repository does not exist"""
        response = test_client.get(
            "/repositories",
            params={"repo_url": "https://github.com/does/not-exist"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestEndToEndIntegration:
    """Test end-to-end integration scenarios"""
    
    @patch('requests.post')
    def test_daifu_chat_with_github_context(self, mock_post, test_client, auth_headers, dummy_repository, mock_daifu_response):
        """Test DAifu chat integration with GitHub context"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "session_id": "test_session",
            "message": {
                "content": "Tell me about my repository test-repo",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
        assert len(data["conversation"]) == 2  # User message + DAifu response
    
    def test_full_workflow_auth_to_github_api(self, test_client, mock_github_api):
        """Test full workflow from authentication to GitHub API usage"""
        # This would be a complex test that simulates:
        # 1. User authentication
        # 2. Repository extraction
        # 3. GitHub API calls
        # 4. Data storage
        # 5. Chat integration
        
        # For now, we'll test the components individually
        # In a real scenario, this would be a comprehensive end-to-end test
        pass


class TestGitHubAPIPerformance:
    """Test GitHub API performance and rate limiting"""
    
    def test_concurrent_api_calls(self, test_client, auth_headers, mock_github_api):
        """Test handling of concurrent GitHub API calls"""
        import concurrent.futures
        
        def make_request():
            with patch('github.github_api.get_github_api', return_value=mock_github_api):
                return test_client.get("/github/repositories", headers=auth_headers)
        
        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for response in results:
            assert response.status_code == 200
    
    def test_api_rate_limiting_simulation(self, test_client, auth_headers):
        """Test GitHub API rate limiting simulation"""
        mock_api = MagicMock()
        mock_api.repos.list_for_authenticated_user.side_effect = Exception("API rate limit exceeded")
        
        with patch('github.github_api.get_github_api', return_value=mock_api):
            response = test_client.get("/github/repositories", headers=auth_headers)
            assert response.status_code == 400
            
            data = response.json()
            assert "Failed to fetch repositories" in data["detail"]
            assert "API rate limit exceeded" in data["detail"]


class TestGitHubAPIValidation:
    """Test GitHub API input validation"""
    
    def test_invalid_repository_owner(self, test_client, auth_headers, mock_github_api):
        """Test invalid repository owner handling"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            response = test_client.get("/github/repositories/invalid-owner/test-repo", headers=auth_headers)
            assert response.status_code == 200  # API call succeeds, but may return different data
    
    def test_invalid_issue_data(self, test_client, auth_headers):
        """Test creating issue with invalid data"""
        invalid_issue_data = {
            "title": "",  # Empty title
            "body": "Test body"
        }
        
        # FastAPI validation should catch this
        response = test_client.post(
            "/github/repositories/testuser/test-repo/issues",
            json=invalid_issue_data,
            headers=auth_headers
        )
        # This might be caught by Pydantic validation
        assert response.status_code in [400, 422]
    
    def test_invalid_search_query(self, test_client, auth_headers, mock_github_api):
        """Test repository search with invalid query"""
        with patch('github.github_api.get_github_api', return_value=mock_github_api):
            # Test with empty query
            response = test_client.get("/github/search/repositories?q=", headers=auth_headers)
            assert response.status_code == 422  # Validation error 