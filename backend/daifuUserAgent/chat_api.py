"""
DaiFu User Agent Chat API with Langfuse Telemetry

This module provides chat API for the DaiFu user agent with comprehensive telemetry
and observability through Langfuse.
"""

import os
import time
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
import requests

from models import ChatRequest, User, ChatSession, ChatMessage
from db.database import get_db
from auth.github_oauth import get_current_user
from utils.langfuse_utils import daifu_agent_trace, log_llm_generation

# Create FastAPI router
router = APIRouter(tags=["daifu"])

class DaiFuAgent:
    """DaiFu User Agent with telemetry support"""
    
    @staticmethod
    @daifu_agent_trace
    def build_daifu_prompt(
        repo_details: Dict[str, Any],
        commits: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        pulls: List[Dict[str, Any]],
        conversation: List[tuple]
    ) -> str:
        """Build DaiFu agent prompt with repository context"""
        
        prompt = f"""You are DaiFu, an intelligent assistant for software development and GitHub repository analysis.

Repository: {repo_details.get('name', 'Unknown')}
Owner: {repo_details.get('owner', 'Unknown')}
Description: {repo_details.get('description', 'No description available')}
Language: {repo_details.get('language', 'Unknown')}
Stars: {repo_details.get('stargazers_count', 0)}

Recent Commits ({len(commits)}):
"""
        
        for commit in commits[:5]:  # Show last 5 commits
            prompt += f"- {commit.get('message', 'No message')[:100]}...\n"
        
        prompt += f"\nOpen Issues ({len(issues)}):\n"
        for issue in issues[:5]:  # Show first 5 issues
            prompt += f"- #{issue.get('number', 'N/A')}: {issue.get('title', 'No title')[:80]}...\n"
        
        prompt += f"\nRecent Pull Requests ({len(pulls)}):\n"
        for pr in pulls[:3]:  # Show first 3 PRs
            prompt += f"- #{pr.get('number', 'N/A')}: {pr.get('title', 'No title')[:80]}...\n"
        
        prompt += "\nConversation History:\n"
        for role, content in conversation[-10:]:  # Last 10 messages
            prompt += f"{role}: {content[:200]}...\n"
        
        prompt += """
Please provide helpful, accurate responses about the repository, code analysis, or development guidance.
Be concise but informative. If you need more specific information, ask clarifying questions.
"""
        return prompt
    
    @staticmethod
    @daifu_agent_trace
    async def generate_response(
        user_message: str,
        repo_context: Dict[str, Any],
        conversation_history: List[tuple],
        user_id: int
    ) -> Dict[str, Any]:
        """Generate DaiFu agent response with full telemetry"""
        
        # Build the prompt
        prompt = DaiFuAgent.build_daifu_prompt(
            repo_details=repo_context.get('repo_details', {}),
            commits=repo_context.get('commits', []),
            issues=repo_context.get('issues', []),
            pulls=repo_context.get('pulls', []),
            conversation=conversation_history + [("User", user_message)]
        )
        
        # Prepare API call
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        model = "deepseek/deepseek-r1-0528:free"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        # Log input data for telemetry
        input_data = {
            "user_message": user_message[:200],
            "prompt_length": len(prompt),
            "repo_name": repo_context.get('repo_details', {}).get('name', 'Unknown'),
            "conversation_length": len(conversation_history),
            "model": model,
            "user_id": user_id
        }
        
        try:
            start_time = time.time()
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            execution_time = time.time() - start_time
            
            # Extract usage information
            usage = result.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            
            # Log the LLM generation for telemetry
            output_data = {
                "response": ai_response[:200],
                "response_length": len(ai_response),
                "tokens_used": tokens_used,
                "execution_time": execution_time
            }
            
            log_llm_generation(
                name="daifu_agent_chat_response",
                model=model,
                input_data=input_data,
                output_data=output_data,
                metadata={
                    "service": "daifu_chat",
                    "agent": "daifu_user_agent",
                    "user_id": user_id,
                    "repo_context": repo_context.get('repo_details', {}).get('name', 'Unknown')
                },
                tokens_used=tokens_used
            )
            
            return {
                "response": ai_response,
                "tokens_used": tokens_used,
                "execution_time": execution_time,
                "model": model,
                "success": True
            }
            
        except requests.RequestException as e:
            # Log error for telemetry
            log_llm_generation(
                name="daifu_agent_chat_response_error",
                model=model,
                input_data=input_data,
                output_data={"error": str(e)},
                metadata={
                    "service": "daifu_chat",
                    "agent": "daifu_user_agent",
                    "user_id": user_id,
                    "error_type": type(e).__name__
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate response: {str(e)}"
            )


@router.post("/chat")
@daifu_agent_trace
async def chat_with_daifu(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with DaiFu agent with comprehensive telemetry
    """
    try:
        # Mock repository context for testing
        # In a real implementation, this would fetch from GitHub API
        repo_context = {
            "repo_details": {
                "name": request.repo_name or "test-repo",
                "owner": request.repo_owner or "test-owner",
                "description": "Test repository for DaiFu agent",
                "language": "Python",
                "stargazers_count": 42
            },
            "commits": [
                {"message": "Fix authentication bug", "sha": "abc123"},
                {"message": "Add new feature", "sha": "def456"},
                {"message": "Update documentation", "sha": "ghi789"}
            ],
            "issues": [
                {"number": 1, "title": "Authentication not working"},
                {"number": 2, "title": "Add dark mode support"}
            ],
            "pulls": [
                {"number": 3, "title": "Feature: User dashboard"},
                {"number": 4, "title": "Fix: Memory leak in background process"}
            ]
        }
        
        # Mock conversation history
        conversation_history = [
            ("Assistant", "Hello! I'm DaiFu, your development assistant. How can I help you today?"),
            ("User", "Can you help me understand this codebase?"),
            ("Assistant", "Of course! I'd be happy to help you understand the codebase. What specific aspects would you like to explore?")
        ]
        
        # Generate response using DaiFu agent
        result = await DaiFuAgent.generate_response(
            user_message=request.message.content,
            repo_context=repo_context,
            conversation_history=conversation_history,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "message": result["response"],
            "metadata": {
                "tokens_used": result["tokens_used"],
                "execution_time": result["execution_time"],
                "model": result["model"],
                "conversation_id": request.conversation_id,
                "agent": "daifu"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat request failed: {str(e)}"
        )


@router.get("/test")
@daifu_agent_trace
async def test_daifu_agent(
    message: str = "Hello DaiFu, can you help me understand this repository?",
    current_user: User = Depends(get_current_user)
):
    """Test endpoint for DaiFu agent"""
    try:
        # Create a test chat request
        from models import ChatMessageInput
        
        test_request = ChatRequest(
            conversation_id="test-conversation",
            message=ChatMessageInput(content=message),
            repo_owner="test-owner",
            repo_name="test-repo"
        )
        
        # Mock database session for testing
        class MockDB:
            def __init__(self):
                pass
                
        mock_db = MockDB()
        
        # Call the chat endpoint
        result = await chat_with_daifu(test_request, mock_db, current_user)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test failed: {str(e)}"
        )
