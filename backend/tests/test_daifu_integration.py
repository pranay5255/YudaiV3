"""
Integration tests for DAifu chat API

These tests verify the integration between DAifu chat and GitHub authentication,
including context sharing and authenticated chat functionality.
"""

from unittest.mock import patch


class TestDaifuChatIntegration:
    """Test DAifu chat integration with GitHub authentication"""
    
    @patch('requests.post')
    def test_daifu_chat_basic(self, mock_post, test_client, mock_daifu_response):
        """Test basic DAifu chat functionality"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "test_conv",
            "message": {
                "content": "Hello DAifu!",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
        assert len(data["conversation"]) == 2  # User message + DAifu response
        assert data["conversation"][0][0] == "User"
        assert data["conversation"][0][1] == "Hello DAifu!"
        assert data["conversation"][1][0] == "DAifu"
    
    @patch('requests.post')
    def test_daifu_chat_with_auth_context(self, mock_post, test_client, auth_headers, dummy_repository, mock_daifu_response):
        """Test DAifu chat with authenticated user context"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "auth_test_conv",
            "message": {
                "content": "Tell me about my repositories",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
        
        # Verify the prompt was built with GitHub context
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        prompt_content = call_args[1]["json"]["messages"][0]["content"]
        
        # Check that GitHub context is included in the prompt
        assert "Repository root: YudaiV3" in prompt_content
        assert "backend/repo_processor/filedeps.py" in prompt_content
    
    @patch('requests.post')
    def test_daifu_chat_conversation_history(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu chat conversation history management"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        conversation_id = "history_test_conv"
        
        # First message
        chat_data_1 = {
            "conversation_id": conversation_id,
            "message": {
                "content": "What is Python?",
                "is_code": False
            },
            "context_cards": []
        }
        
        response_1 = test_client.post("/chat/daifu", json=chat_data_1)
        assert response_1.status_code == 200
        
        data_1 = response_1.json()
        assert len(data_1["conversation"]) == 2
        
        # Second message in same conversation
        chat_data_2 = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Tell me more about it",
                "is_code": False
            },
            "context_cards": []
        }
        
        response_2 = test_client.post("/chat/daifu", json=chat_data_2)
        assert response_2.status_code == 200
        
        data_2 = response_2.json()
        assert len(data_2["conversation"]) == 4  # 2 previous + 2 new
        
        # Verify conversation history is maintained
        assert data_2["conversation"][0][1] == "What is Python?"
        assert data_2["conversation"][2][1] == "Tell me more about it"
    
    @patch('requests.post')
    def test_daifu_chat_with_code_message(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu chat with code message"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "code_test_conv",
            "message": {
                "content": "def hello():\n    print('Hello, World!')",
                "is_code": True
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
        assert data["conversation"][0][1] == "def hello():\n    print('Hello, World!')"
    
    @patch('requests.post')
    def test_daifu_chat_with_context_cards(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu chat with context cards"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "context_test_conv",
            "message": {
                "content": "Explain this code",
                "is_code": False
            },
            "context_cards": ["card1", "card2"]
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
    
    def test_daifu_chat_missing_openrouter_key(self, test_client):
        """Test DAifu chat with missing OpenRouter API key"""
        chat_data = {
            "conversation_id": "error_test_conv",
            "message": {
                "content": "Hello",
                "is_code": False
            },
            "context_cards": []
        }
        
        # Mock missing API key
        with patch('os.getenv', return_value=None):
            response = test_client.post("/chat/daifu", json=chat_data)
            assert response.status_code == 500
            
            data = response.json()
            assert "OPENROUTER_API_KEY not configured" in data["detail"]
    
    @patch('requests.post')
    def test_daifu_chat_api_error(self, mock_post, test_client):
        """Test DAifu chat with API error"""
        # Mock API error
        mock_post.side_effect = Exception("API Error")
        
        chat_data = {
            "conversation_id": "api_error_test_conv",
            "message": {
                "content": "Hello",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 500
        
        data = response.json()
        assert "LLM call failed" in data["detail"]
    
    @patch('requests.post')
    def test_daifu_chat_timeout(self, mock_post, test_client):
        """Test DAifu chat with timeout"""
        # Mock timeout
        mock_post.side_effect = Exception("Request timeout")
        
        chat_data = {
            "conversation_id": "timeout_test_conv",
            "message": {
                "content": "Hello",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 500
        
        data = response.json()
        assert "LLM call failed" in data["detail"]


class TestDaifuPromptIntegration:
    """Test DAifu prompt building with GitHub context"""
    
    @patch('requests.post')
    def test_prompt_includes_github_context(self, mock_post, test_client, mock_daifu_response):
        """Test that prompts include GitHub context"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "prompt_test_conv",
            "message": {
                "content": "Help me with my code",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 200
        
        # Verify the prompt was built with GitHub context
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        prompt_content = call_args[1]["json"]["messages"][0]["content"]
        
        # Check that GitHub context is included
        assert "Repository root: YudaiV3" in prompt_content
        assert "src/components/Chat.tsx" in prompt_content
        assert "src/App.tsx" in prompt_content
        assert "backend/repo_processor/filedeps.py" in prompt_content
    
    @patch('requests.post')
    def test_prompt_includes_conversation_history(self, mock_post, test_client, mock_daifu_response):
        """Test that prompts include conversation history"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        conversation_id = "history_prompt_test"
        
        # First message
        chat_data_1 = {
            "conversation_id": conversation_id,
            "message": {
                "content": "What is FastAPI?",
                "is_code": False
            },
            "context_cards": []
        }
        
        test_client.post("/chat/daifu", json=chat_data_1)
        
        # Second message
        chat_data_2 = {
            "conversation_id": conversation_id,
            "message": {
                "content": "How do I use it?",
                "is_code": False
            },
            "context_cards": []
        }
        
        test_client.post("/chat/daifu", json=chat_data_2)
        
        # Check the second call includes history
        assert mock_post.call_count == 2
        second_call_args = mock_post.call_args_list[1]
        second_prompt_content = second_call_args[1]["json"]["messages"][0]["content"]
        
        # Should include previous conversation
        assert "What is FastAPI?" in second_prompt_content
        assert "How do I use it?" in second_prompt_content


class TestDaifuAuthenticationIntegration:
    """Test DAifu integration with GitHub authentication"""
    
    @patch('requests.post')
    def test_daifu_with_authenticated_user(self, mock_post, test_client, auth_headers, dummy_user, mock_daifu_response):
        """Test DAifu chat with authenticated user"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "auth_user_test",
            "message": {
                "content": "Hello, I'm authenticated!",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
    
    @patch('requests.post')
    def test_daifu_with_unauthenticated_user(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu chat with unauthenticated user"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "unauth_user_test",
            "message": {
                "content": "Hello, I'm not authenticated!",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
    
    @patch('requests.post')
    def test_daifu_with_repository_context(self, mock_post, test_client, auth_headers, dummy_repository, mock_daifu_response):
        """Test DAifu chat with repository context"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        chat_data = {
            "conversation_id": "repo_context_test",
            "message": {
                "content": "Tell me about my test-repo repository",
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "conversation" in data
        
        # The user has a repository in the database
        # DAifu should have access to this context through the GitHub integration


class TestDaifuValidation:
    """Test DAifu input validation"""
    
    def test_daifu_missing_message_content(self, test_client):
        """Test DAifu chat with missing message content"""
        chat_data = {
            "conversation_id": "validation_test",
            "message": {
                "is_code": False
            },  # Missing content
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 422  # Validation error
    
    def test_daifu_empty_message_content(self, test_client):
        """Test DAifu chat with empty message content"""
        chat_data = {
            "conversation_id": "validation_test",
            "message": {
                "content": "",  # Empty content
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 422  # Validation error
    
    def test_daifu_too_long_message_content(self, test_client):
        """Test DAifu chat with too long message content"""
        chat_data = {
            "conversation_id": "validation_test",
            "message": {
                "content": "x" * 10001,  # Too long content
                "is_code": False
            },
            "context_cards": []
        }
        
        response = test_client.post("/chat/daifu", json=chat_data)
        assert response.status_code == 422  # Validation error
    
    def test_daifu_invalid_conversation_id(self, test_client, mock_daifu_response):
        """Test DAifu chat with invalid conversation ID"""
        # Test with None conversation_id (should default to "default")
        chat_data = {
            "conversation_id": None,
            "message": {
                "content": "Hello",
                "is_code": False
            },
            "context_cards": []
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_daifu_response
            
            response = test_client.post("/chat/daifu", json=chat_data)
            assert response.status_code == 200


class TestDaifuPerformance:
    """Test DAifu performance and concurrent usage"""
    
    @patch('requests.post')
    def test_daifu_concurrent_conversations(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu with concurrent conversations"""
        import concurrent.futures
        
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        def make_chat_request(conv_id):
            chat_data = {
                "conversation_id": f"concurrent_test_{conv_id}",
                "message": {
                    "content": f"Hello from conversation {conv_id}",
                    "is_code": False
                },
                "context_cards": []
            }
            return test_client.post("/chat/daifu", json=chat_data)
        
        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_chat_request, i) for i in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for response in results:
            assert response.status_code == 200
            data = response.json()
            assert "reply" in data
            assert "conversation" in data
    
    @patch('requests.post')
    def test_daifu_memory_usage(self, mock_post, test_client, mock_daifu_response):
        """Test DAifu memory usage with many conversations"""
        # Mock the OpenRouter API response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_daifu_response
        
        # Create many conversations
        for i in range(100):
            chat_data = {
                "conversation_id": f"memory_test_{i}",
                "message": {
                    "content": f"Message {i}",
                    "is_code": False
                },
                "context_cards": []
            }
            
            response = test_client.post("/chat/daifu", json=chat_data)
            assert response.status_code == 200
        
        # All conversations should be stored in memory
        # Note: In production, you'd want to implement conversation cleanup 