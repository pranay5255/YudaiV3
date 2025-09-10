# DAifu Prompt Template
"""Utility to build prompts for the DAifu agent with GitHub context integration."""
import asyncio
import logging
import time
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from .githubOps import GitHubOps

logger = logging.getLogger(__name__)

# Simple in-memory cache for GitHub repository data
# Key: f"{repo_owner}/{repo_name}", Value: (data, timestamp)
_github_cache = {}
_CACHE_TTL = 300  # 5 minutes cache TTL


def _get_cached_github_data(repo_key: str) -> Optional[Dict[str, Any]]:
    """Get cached GitHub data if available and not expired"""
    if repo_key in _github_cache:
        data, timestamp = _github_cache[repo_key]
        if time.time() - timestamp < _CACHE_TTL:
            logger.debug(f"Using cached GitHub data for {repo_key}")
            return data
        else:
            # Remove expired cache entry
            del _github_cache[repo_key]
    return None


def _set_cached_github_data(repo_key: str, data: Dict[str, Any]) -> None:
    """Cache GitHub data"""
    _github_cache[repo_key] = (data, time.time())
    logger.debug(f"Cached GitHub data for {repo_key}")


SYSTEM_HEADER = dedent(
    """
    You are **DAifu**, an AI assistant specialized in GitHub repository management and issue creation.
    Your primary role is to help users create clear, actionable GitHub issues from their conversations
    and repository context.

    **Core Responsibilities:**
    1. Analyze user requests and repository context to create well-structured GitHub issues
    2. Provide direct, professional responses based on available context
    3. Suggest next steps and improvements when appropriate
    4. Maintain focus on actionable outcomes

    **Response Guidelines:**
    - Be direct and professional in all communications
    - Use repository context to provide informed responses
    - Focus on creating clear, actionable GitHub issues when requested
    - Ask for clarification only when essential information is missing
    - Provide specific recommendations based on repository data

    **Output Format:**
    When creating issues, structure them with:
    - Clear, descriptive titles
    - Detailed descriptions including context and requirements
    - Appropriate labels and metadata
    """
).strip()


async def build_daifu_prompt_with_github_context(
    db: Session,
    user_id: int,
    repo_owner: str,
    repo_name: str,
    repo_branch: str,
    conversation: List[Tuple[str, str]],
    file_contexts: List[str] = None,
    fetch_limit: int = 3,  # Reduced from 5 to 3 for faster response
    timeout_seconds: int = 10  # 10 second timeout for GitHub calls
) -> str:
    """
    Build DAifu prompt with real-time GitHub context fetching.

    Args:
        db: Database session
        user_id: User ID for authentication
        repo_owner: Repository owner
        repo_name: Repository name
        repo_branch: Repository branch
        conversation: List of (speaker, message) tuples
        file_contexts: Optional list of file context strings
        fetch_limit: Maximum number of items to fetch for each GitHub resource
        timeout_seconds: Timeout for GitHub API calls

    Returns:
        Complete prompt string with GitHub context
    """
    async def fetch_with_timeout(coro, default_value, description: str):
        """Helper to fetch data with timeout"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {description} for {repo_owner}/{repo_name}")
            return default_value
        except Exception as e:
            logger.warning(f"Error fetching {description} for {repo_owner}/{repo_name}: {e}")
            return default_value

    try:
        # Prepare basic fallback data first
        fallback_repo_details = {
            "full_name": f"{repo_owner}/{repo_name}",
            "name": repo_name,
            "description": "",
            "default_branch": repo_branch,
            "language": "",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 0,
            "html_url": f"https://github.com/{repo_owner}/{repo_name}",
            "topics": [],
        }

        # Check cache first
        repo_key = f"{repo_owner}/{repo_name}"
        cached_data = _get_cached_github_data(repo_key)
        if cached_data:
            logger.debug(f"Using cached GitHub context for {repo_key}")
            return build_daifu_prompt(
                cached_data.get("repo_details", fallback_repo_details),
                cached_data.get("commits", []),
                cached_data.get("issues", []),
                cached_data.get("branches", []),
                conversation,
                file_contexts
            )

        # Initialize GitHub operations
        github_ops = GitHubOps(db)

        # Make concurrent API calls with timeout handling
        try:
            # Fetch all data concurrently with timeout
            repo_details, commits, issues, branches = await asyncio.gather(
                fetch_with_timeout(
                    github_ops.fetch_repository_info_detailed(repo_owner, repo_name, user_id),
                    fallback_repo_details,
                    "repository details"
                ),
                fetch_with_timeout(
                    github_ops.fetch_repository_commits(repo_owner, repo_name, user_id, fetch_limit),
                    [],
                    "repository commits"
                ),
                fetch_with_timeout(
                    github_ops.fetch_repository_issues(repo_owner, repo_name, user_id, fetch_limit),
                    [],
                    "repository issues"
                ),
                fetch_with_timeout(
                    github_ops.fetch_repository_branches(repo_owner, repo_name, user_id),
                    [],
                    "repository branches"
                ),
                return_exceptions=True
            )

            # Handle any exceptions from gather
            if isinstance(repo_details, Exception) or not repo_details:
                repo_details = fallback_repo_details
            if isinstance(commits, Exception):
                commits = []
            if isinstance(issues, Exception):
                issues = []
            if isinstance(branches, Exception):
                branches = []

        except Exception as e:
            logger.error(f"Error in concurrent GitHub API calls: {e}")
            # Fallback to basic data
            repo_details = fallback_repo_details
            commits = []
            issues = []
            branches = []

        # Truncate long data to reduce prompt size and processing time
        truncated_commits = []
        for commit in commits[:2]:  # Only keep 2 most recent commits
            truncated_commits.append({
                "sha": commit.get("sha", "")[:7],
                "message": commit.get("message", "")[:50],  # Truncate long messages
                "author": commit.get("author"),
                "date": commit.get("date")
            })

        truncated_issues = []
        for issue in issues[:2]:  # Only keep 2 most recent issues
            truncated_issues.append({
                "number": issue.get("number"),
                "title": issue.get("title", "")[:50],  # Truncate long titles
                "state": issue.get("state")
            })

        truncated_branches = branches[:3]  # Only keep 3 branches

        # Cache the truncated data for future use
        cache_data = {
            "repo_details": repo_details,
            "commits": truncated_commits,
            "issues": truncated_issues,
            "branches": truncated_branches
        }
        _set_cached_github_data(repo_key, cache_data)

        # Build the prompt with the truncated data
        return build_daifu_prompt(repo_details, truncated_commits, truncated_issues, truncated_branches, conversation, file_contexts)

    except Exception as e:
        logger.error(f"Error building prompt with GitHub context: {e}")
        # Fallback to basic prompt without GitHub context
        repo_details = {
            "full_name": f"{repo_owner}/{repo_name}",
            "name": repo_name,
            "description": "",
            "default_branch": repo_branch,
            "language": "",
            "stargazers_count": 0,
            "forks_count": 0,
            "open_issues_count": 0,
            "html_url": f"https://github.com/{repo_owner}/{repo_name}",
            "topics": [],
        }
        return build_daifu_prompt(repo_details, [], [], [], conversation, file_contexts)


def build_daifu_prompt(
    repo_details: Dict[str, Any],
    commits: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    branches: List[Dict[str, Any]],
    conversation: List[Tuple[str, str]],
    file_contexts: Optional[List[str]] = None
) -> str:
    """Return the complete prompt string for DAifu."""
    # Format repository details
    details_str = (
        f"Repository: {repo_details['full_name']}\n"
        f"Description: {repo_details.get('description','')}\n"
        f"Default branch: {repo_details.get('default_branch','')}\n"
        f"Languages: {', '.join(repo_details.get('languages', {}).keys())}\n"
        f"Topics: {', '.join(repo_details.get('topics', []))}\n"
        f"License: {repo_details.get('license', {}).get('name') if repo_details.get('license') else 'None'}\n"
        f"Stars: {repo_details.get('stargazers_count',0)}, Forks: {repo_details.get('forks_count',0)}\n"
        f"Open issues: {repo_details.get('open_issues_count',0)}\n"
        f"URL: {repo_details.get('html_url','')}\n"
    )

    # Format recent commits (limit to 5 for brevity)
    commits_str = "Recent Commits:\n"
    for c in commits[:5]:
        commits_str += (
            f"- {c['sha'][:7]}: {c['message'].splitlines()[0]} "
            f"(by {c['author'].get('name','?')} at {c['author'].get('date','')})\n"
        )

    # Format open issues (limit to 5)
    issues_str = "Open Issues:\n"
    open_issues = [i for i in issues if i['state'] == 'open'][:5]
    for i in open_issues:
        issues_str += (
            f"- #{i['number']}: {i['title']} (by {i['user'].get('login','?')})\n"
        )

    # Format repository branches (limit to 5)
    branches_str = "Repository Branches:\n"
    for b in branches[:5]:
        branches_str += (
            f"- {b.get('name', 'unknown')}\n"
        )

    # Format file contexts if provided
    file_contexts_str = ""
    if file_contexts:
        file_contexts_str = "Relevant File Contexts:\n" + "\n".join(file_contexts)

    # Format conversation
    convo_formatted = "\n".join(f"{speaker}: {utterance}" for speaker, utterance in conversation)

    # Combine all into final prompt
    prompt = dedent(
        f"""
        {SYSTEM_HEADER}

        <GITHUB_CONTEXT_BEGIN>
        {details_str}
        {commits_str}
        {issues_str}
        {branches_str}
        </GITHUB_CONTEXT_END>

        <FILE_CONTEXTS_BEGIN>
        {file_contexts_str}
        </FILE_CONTEXTS_END>

        <CONVERSATION_BEGIN>
        {convo_formatted}
        </CONVERSATION_END>

        (Respond now as **DAifu** following the guidelines above. Focus on providing direct, actionable responses based on the available context.)
        """
    ).strip()
    return prompt

# Note: GitHub context fetching is now handled by ChatOps class using GitHubOps
# This ensures consistent data fetching and error handling across the application