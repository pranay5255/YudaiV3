"""
Code Inspector Agent Service

This service analyzes codebases and generates GitHub issues based on findings.
It's an internal agent class used by the backend, not an API service.
"""

import json
import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from models import (
    UserIssue, 
    CreateUserIssueRequest,
    Repository
)
from .promptTemplate import (
    build_code_inspector_prompt,
    build_issue_refinement_prompt,
    build_swe_agent_preparation_prompt
)


class CodeInspectorAgent:
    """
    Internal agent class for analyzing codebases and generating GitHub issues.
    
    This agent:
    1. Analyzes codebase using LLM calls
    2. Generates GitHub issues in JSON format
    3. Parses and stores issues in the database
    4. Prepares issues for SWE agent processing
    """
    
    def __init__(self, openrouter_api_key: Optional[str] = None):
        """Initialize the code inspector agent."""
        self.api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        
        self.model = "deepseek/deepseek-r1-0528:free"
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def _make_llm_call(self, prompt: str, max_tokens: int = 4000) -> str:
        """Make a call to OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Lower temperature for more consistent analysis
        }
        
        try:
            resp = requests.post(
                self.base_url,
                headers=headers,
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}")
    
    def _build_codebase_context(self, repository: Repository) -> str:
        """Build codebase context from repository data."""
        context = f"""
Repository: {repository.full_name}
Owner: {repository.owner}
Language: {repository.language or 'Unknown'}
Description: {repository.description or 'No description'}

Key Information:
- Stars: {repository.stargazers_count}
- Forks: {repository.forks_count}
- Open Issues: {repository.open_issues_count}
- Last Updated: {repository.github_updated_at}
"""
        
        # Add file structure if available
        if repository.file_items:
            context += "\n\nFile Structure:\n"
            for file_item in repository.file_items[:20]:  # Limit to first 20 files
                context += f"- {file_item.path} ({file_item.file_type}, {file_item.tokens} tokens)\n"
        
        return context
    
    def _parse_issues_from_response(self, llm_response: str) -> List[Dict[str, Any]]:
        """Parse GitHub issues from LLM response."""
        issues = []
        
        # Find the "ISSUES IDENTIFIED" section
        lines = llm_response.split('\n')
        in_issues_section = False
        
        for line in lines:
            line = line.strip()
            
            if "ISSUES IDENTIFIED" in line:
                in_issues_section = True
                continue
                
            if in_issues_section and line.startswith('{"'):
                try:
                    # Parse the JSON line
                    issue_data = json.loads(line)
                    
                    # Validate required fields
                    if all(key in issue_data for key in ['title', 'body', 'priority', 'category']):
                        # Ensure lists are lists
                        issue_data['labels'] = issue_data.get('labels', [])
                        issue_data['affected_files'] = issue_data.get('affected_files', [])
                        issue_data['acceptance_criteria'] = issue_data.get('acceptance_criteria', [])
                        issue_data['dependencies'] = issue_data.get('dependencies', [])
                        
                        # Set defaults
                        issue_data['complexity'] = issue_data.get('complexity', 'M')
                        issue_data['estimated_hours'] = issue_data.get('estimated_hours', 2)
                        
                        issues.append(issue_data)
                        
                except json.JSONDecodeError as e:
                    print(f"Failed to parse issue JSON: {line[:100]}... Error: {e}")
                    continue
            
            # Stop when we hit another section
            elif in_issues_section and line.startswith('###'):
                break
        
        return issues
    
    def analyze_repository(
        self,
        db: Session,
        repository_id: int,
        user_id: int,
        analysis_type: str = "comprehensive",
        focus_areas: Optional[List[str]] = None
    ) -> List[UserIssue]:
        """
        Analyze a repository and generate GitHub issues.
        
        Args:
            db: Database session
            repository_id: ID of repository to analyze
            user_id: ID of user requesting analysis
            analysis_type: Type of analysis to perform
            focus_areas: Specific areas to focus on
            
        Returns:
            List of created UserIssue objects
        """
        
        # Get repository from database
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository with ID {repository_id} not found")
        
        # Build codebase context
        codebase_context = self._build_codebase_context(repository)
        
        # Build repository info
        repository_info = {
            'owner': repository.owner,
            'name': repository.name,
            'language': repository.language,
            'description': repository.description
        }
        
        # Generate analysis prompt
        prompt = build_code_inspector_prompt(
            codebase_context=codebase_context,
            analysis_type=analysis_type,
            focus_areas=focus_areas,
            repository_info=repository_info
        )
        
        # Make LLM call for analysis
        print(f"Analyzing repository {repository.full_name}...")
        llm_response = self._make_llm_call(prompt, max_tokens=6000)
        
        # Parse issues from response
        parsed_issues = self._parse_issues_from_response(llm_response)
        print(f"Found {len(parsed_issues)} issues from analysis")
        
        # Create UserIssue objects in database
        created_issues = []
        
        for issue_data in parsed_issues:
            # Create issue request
            issue_request = CreateUserIssueRequest(
                title=issue_data['title'],
                issue_text_raw=json.dumps(issue_data),  # Store full JSON as raw text
                description=issue_data['body'],
                repo_owner=repository.owner,
                repo_name=repository.name,
                priority=issue_data['priority'],
                issue_steps=issue_data.get('acceptance_criteria', [])
            )
            
            # Create UserIssue in database
            user_issue = UserIssue(
                user_id=user_id,
                issue_id=str(uuid.uuid4()),
                title=issue_request.title,
                description=issue_request.description,
                issue_text_raw=issue_request.issue_text_raw,
                issue_steps=issue_request.issue_steps,
                repo_owner=issue_request.repo_owner,
                repo_name=issue_request.repo_name,
                priority=issue_request.priority,
                status="pending",
                created_at=datetime.utcnow()
            )
            
            db.add(user_issue)
            created_issues.append(user_issue)
        
        # Commit all issues
        db.commit()
        
        print(f"Created {len(created_issues)} issues in database")
        return created_issues
    
    def refine_issues(
        self,
        db: Session,
        repository_id: int,
        raw_issues: List[UserIssue]
    ) -> List[UserIssue]:
        """
        Refine and validate generated issues to remove duplicates and improve quality.
        
        Args:
            db: Database session
            repository_id: Repository ID
            raw_issues: List of raw issues to refine
            
        Returns:
            List of refined UserIssue objects
        """
        
        # Get repository context
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository with ID {repository_id} not found")
        
        repository_context = self._build_codebase_context(repository)
        
        # Get existing issues to avoid duplicates
        existing_issues = db.query(UserIssue).filter(
            UserIssue.repo_owner == repository.owner,
            UserIssue.repo_name == repository.name,
            UserIssue.status != "cancelled"
        ).all()
        
        existing_issue_data = [
            {"title": issue.title, "body": issue.description}
            for issue in existing_issues
        ]
        
        # Prepare raw issue data for refinement
        raw_issue_data = "\n".join([
            issue.issue_text_raw for issue in raw_issues
        ])
        
        # Build refinement prompt
        refinement_prompt = build_issue_refinement_prompt(
            raw_issue_data=raw_issue_data,
            repository_context=repository_context,
            existing_issues=existing_issue_data
        )
        
        # Make LLM call for refinement
        print("Refining issues...")
        refined_response = self._make_llm_call(refinement_prompt, max_tokens=6000)
        
        # Parse refined issues
        refined_issues_data = []
        for line in refined_response.split('\n'):
            line = line.strip()
            if line.startswith('{"'):
                try:
                    issue_data = json.loads(line)
                    refined_issues_data.append(issue_data)
                except json.JSONDecodeError:
                    continue
        
        print(f"Refined to {len(refined_issues_data)} issues")
        
        # Update existing issues or create new ones
        refined_issues = []
        for i, refined_data in enumerate(refined_issues_data):
            if i < len(raw_issues):
                # Update existing issue
                issue = raw_issues[i]
                issue.title = refined_data['title']
                issue.description = refined_data['body']
                issue.issue_text_raw = json.dumps(refined_data)
                issue.priority = refined_data.get('priority', 'medium')
                issue.issue_steps = refined_data.get('acceptance_criteria', [])
                refined_issues.append(issue)
        
        # Remove excess issues if refinement reduced the count
        for i in range(len(refined_issues_data), len(raw_issues)):
            raw_issues[i].status = "cancelled"
        
        db.commit()
        return refined_issues
    
    def prepare_for_swe_agent(
        self,
        db: Session,
        user_issue: UserIssue
    ) -> Dict[str, Any]:
        """
        Prepare a user issue for SWE agent processing.
        
        Args:
            db: Database session
            user_issue: UserIssue to prepare
            
        Returns:
            Dictionary with SWE agent execution plan
        """
        
        # Get repository context
        repository = db.query(Repository).filter(
            Repository.owner == user_issue.repo_owner,
            Repository.name == user_issue.repo_name
        ).first()
        
        if not repository:
            raise ValueError(f"Repository {user_issue.repo_owner}/{user_issue.repo_name} not found")
        
        codebase_context = self._build_codebase_context(repository)
        
        # Parse the issue data from JSON
        try:
            github_issue = json.loads(user_issue.issue_text_raw)
        except json.JSONDecodeError:
            # Fallback to basic issue structure
            github_issue = {
                'title': user_issue.title,
                'body': user_issue.description,
                'priority': user_issue.priority,
                'complexity': 'M',
                'category': 'unknown',
                'affected_files': [],
                'acceptance_criteria': user_issue.issue_steps or []
            }
        
        # Build preparation prompt
        preparation_prompt = build_swe_agent_preparation_prompt(
            github_issue=github_issue,
            codebase_context=codebase_context
        )
        
        # Make LLM call for preparation
        print(f"Preparing issue '{user_issue.title}' for SWE agent...")
        preparation_response = self._make_llm_call(preparation_prompt, max_tokens=4000)
        
        # Parse the execution plan
        try:
            # Find JSON in response
            for line in preparation_response.split('\n'):
                line = line.strip()
                if line.startswith('{'):
                    execution_plan = json.loads(line)
                    
                    # Update the user issue with SWE agent data
                    user_issue.agent_response = json.dumps(execution_plan)
                    user_issue.status = "ready_for_swe"
                    db.commit()
                    
                    return execution_plan
        except json.JSONDecodeError as e:
            print(f"Failed to parse SWE preparation response: {e}")
            
        raise ValueError("Failed to generate valid SWE agent execution plan")


class CodeInspectorService:
    """
    Service class for managing code inspector agent operations.
    """
    
    @staticmethod
    def analyze_repository_and_create_issues(
        db: Session,
        repository_id: int,
        user_id: int,
        analysis_type: str = "comprehensive",
        focus_areas: Optional[List[str]] = None,
        refine_issues: bool = True
    ) -> List[UserIssue]:
        """
        Complete workflow: analyze repository, create issues, and optionally refine them.
        
        Args:
            db: Database session
            repository_id: Repository to analyze
            user_id: User requesting analysis
            analysis_type: Type of analysis
            focus_areas: Specific focus areas
            refine_issues: Whether to refine issues after generation
            
        Returns:
            List of created UserIssue objects
        """
        
        agent = CodeInspectorAgent()
        
        # Step 1: Analyze repository and create initial issues
        issues = agent.analyze_repository(
            db=db,
            repository_id=repository_id,
            user_id=user_id,
            analysis_type=analysis_type,
            focus_areas=focus_areas
        )
        
        # Step 2: Optionally refine issues
        if refine_issues and issues:
            issues = agent.refine_issues(
                db=db,
                repository_id=repository_id,
                raw_issues=issues
            )
        
        return issues
    
    @staticmethod
    def prepare_issue_for_swe_agent(
        db: Session,
        issue_id: str
    ) -> Dict[str, Any]:
        """
        Prepare a specific issue for SWE agent processing.
        
        Args:
            db: Database session
            issue_id: ID of the UserIssue to prepare
            
        Returns:
            SWE agent execution plan
        """
        
        # Get the issue
        user_issue = db.query(UserIssue).filter(UserIssue.issue_id == issue_id).first()
        if not user_issue:
            raise ValueError(f"Issue with ID {issue_id} not found")
        
        agent = CodeInspectorAgent()
        return agent.prepare_for_swe_agent(db, user_issue)
    
    @staticmethod
    def get_issues_ready_for_swe(db: Session, repository_id: int) -> List[UserIssue]:
        """
        Get all issues that are ready for SWE agent processing.
        
        Args:
            db: Database session
            repository_id: Repository ID
            
        Returns:
            List of UserIssue objects ready for SWE processing
        """
        
        repository = db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository with ID {repository_id} not found")
        
        return db.query(UserIssue).filter(
            UserIssue.repo_owner == repository.owner,
            UserIssue.repo_name == repository.name,
            UserIssue.status.in_(["ready_for_swe", "pending"])
        ).all() 