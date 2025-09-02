#!/usr/bin/env python3
"""
GitHub Operations Module - Centralized GitHub API Operations

This module provides all GitHub API operations for the DAifu Agent,
consolidating functionality previously scattered across multiple files.
It uses the ghapi library for GitHub API interactions and integrates
with the existing OAuth authentication system.

Features:
- Repository information fetching
- Issue creation and management
- Branch and contributor information
- Commit history access
- OAuth token management
- Error handling and rate limiting

Dependencies:
- ghapi: GitHub API client library
- httpx: HTTP client for API calls
- Existing OAuth infrastructure

Author: DAifu Agent
"""

import logging
from typing import Any, Dict, List, Optional

from auth.github_oauth import get_github_api
from ghapi.all import GhApi
from models import AuthToken
from sqlalchemy.orm import Session

from utils import utc_now

# Configure logging
logger = logging.getLogger(__name__)


class GitHubOpsError(Exception):
    """Custom exception for GitHubOps operations"""

    pass


class GitHubOps:
    """
    Centralized GitHub Operations Class

    Provides all GitHub API functionality including:
    - Repository operations (info, branches, contributors, commits)
    - Issue operations (creation, listing, updates)
    - Authentication and token management
    - Error handling and rate limiting
    """

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def get_user_github_token(user_id: int, db: Session) -> Optional[str]:
        """
        Get user's active GitHub access token

        Args:
            user_id: User ID
            db: Database session

        Returns:
            GitHub access token or None if not found/expired
        """
        try:
            auth_token = (
                db.query(AuthToken)
                .filter(AuthToken.user_id == user_id, AuthToken.is_active)
                .first()
            )

            if not auth_token:
                logger.warning(f"No active GitHub token found for user {user_id}")
                return None

            # Check if token is expired
            if auth_token.expires_at and auth_token.expires_at < utc_now():
                logger.warning(f"GitHub token expired for user {user_id}")
                auth_token.is_active = False
                db.commit()
                return None

            return auth_token.access_token

        except Exception as e:
            logger.error(f"Failed to get GitHub token for user {user_id}: {e}")
            return None

    def get_github_client(self, user_id: int) -> Optional[GhApi]:
        """
        Get authenticated GitHub API client for a user

        Args:
            user_id: User ID

        Returns:
            GhApi client instance or None if authentication fails
        """
        try:
            return get_github_api(user_id, self.db)
        except Exception as e:
            logger.error(f"Failed to get GitHub client for user {user_id}: {e}")
            return None

    async def fetch_repository_info(
        self, owner: str, repo: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Fetch basic repository information

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication

        Returns:
            Repository information dictionary
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching repository info for {owner}/{repo}")

            # Use ghapi to get repository information
            repo_data = client.repos.get(owner, repo)

            return {
                "name": repo_data.get("name", ""),
                "description": repo_data.get("description", ""),
                "language": repo_data.get("language", ""),
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "issues": repo_data.get("open_issues_count", 0),
                "default_branch": repo_data.get("default_branch", "main"),
                "topics": repo_data.get("topics", []),
                "updated_at": repo_data.get("updated_at", ""),
                "html_url": repo_data.get("html_url", ""),
                "private": repo_data.get("private", False),
                "archived": repo_data.get("archived", False),
            }

        except Exception as e:
            logger.error(f"Error fetching repository info for {owner}/{repo}: {e}")
            return {"name": repo, "owner": owner, "error": str(e)}

    async def fetch_repository_info_detailed(
        self, owner: str, repo: str, user_id: int
    ) -> Dict[str, Any]:
        """
        Fetch detailed repository information

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication

        Returns:
            Detailed repository information dictionary
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching detailed repository info for {owner}/{repo}")

            # Use ghapi to get detailed repository information
            repo_data = client.repos.get(owner, repo)

            return {
                "id": repo_data.get("id"),
                "name": repo_data.get("name"),
                "full_name": repo_data.get("full_name"),
                "private": repo_data.get("private"),
                "html_url": repo_data.get("html_url"),
                "description": repo_data.get("description"),
                "language": repo_data.get("language"),
                "stargazers_count": repo_data.get("stargazers_count"),
                "forks_count": repo_data.get("forks_count"),
                "open_issues_count": repo_data.get("open_issues_count"),
                "default_branch": repo_data.get("default_branch"),
                "topics": repo_data.get("topics", []),
                "created_at": repo_data.get("created_at"),
                "updated_at": repo_data.get("updated_at"),
                "pushed_at": repo_data.get("pushed_at"),
                "size": repo_data.get("size"),
                "has_issues": repo_data.get("has_issues"),
                "has_projects": repo_data.get("has_projects"),
                "has_wiki": repo_data.get("has_wiki"),
                "has_pages": repo_data.get("has_pages"),
                "has_downloads": repo_data.get("has_downloads"),
                "archived": repo_data.get("archived"),
                "disabled": repo_data.get("disabled"),
            }

        except Exception as e:
            logger.error(
                f"Error fetching detailed repository info for {owner}/{repo}: {e}"
            )
            return {"name": repo, "full_name": f"{owner}/{repo}", "error": str(e)}

    async def fetch_repository_issues(
        self, owner: str, repo: str, user_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent repository issues

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication
            limit: Maximum number of issues to fetch

        Returns:
            List of recent issues
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching repository issues for {owner}/{repo}")

            # Use ghapi to get repository issues
            issues_data = client.issues.list_for_repo(
                owner,
                repo,
                state="open",
                sort="created",
                direction="desc",
                per_page=limit,
            )

            issues = []
            for issue in issues_data[:limit]:
                if not issue.get("pull_request"):  # Exclude PRs
                    issues.append(
                        {
                            "number": issue.get("number"),
                            "title": issue.get("title", "")[
                                :100
                            ],  # Truncate long titles
                            "state": issue.get("state"),
                            "created_at": issue.get("created_at"),
                            "updated_at": issue.get("updated_at"),
                            "labels": [
                                label.get("name") for label in issue.get("labels", [])
                            ],
                            "assignee": issue.get("assignee", {}).get("login")
                            if issue.get("assignee")
                            else None,
                            "comments": issue.get("comments", 0),
                            "html_url": issue.get("html_url"),
                        }
                    )

            return issues

        except Exception as e:
            logger.error(f"Error fetching repository issues for {owner}/{repo}: {e}")
            return []

    async def fetch_repository_commits(
        self, owner: str, repo: str, user_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent repository commits

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication
            limit: Maximum number of commits to fetch

        Returns:
            List of recent commits
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching repository commits for {owner}/{repo}")

            # Use ghapi to get repository commits
            commits_data = client.repos.list_commits(owner, repo, per_page=limit)

            commits = []
            for commit in commits_data[:limit]:
                commit_info = commit.get("commit", {})
                author = commit_info.get("author", {})
                committer = commit_info.get("committer", {})

                commits.append(
                    {
                        "sha": commit.get("sha", "")[:7],  # Short SHA
                        "message": commit_info.get("message", "")[:100],  # Truncate
                        "author": author.get("name"),
                        "author_email": author.get("email"),
                        "committer": committer.get("name"),
                        "committer_email": committer.get("email"),
                        "date": author.get("date"),
                        "html_url": commit.get("html_url"),
                        "committer_date": committer.get("date"),
                    }
                )

            return commits

        except Exception as e:
            logger.error(f"Error fetching repository commits for {owner}/{repo}: {e}")
            return []

    async def fetch_repository_branches(
        self, owner: str, repo: str, user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch repository branches

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication

        Returns:
            List of repository branches
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching repository branches for {owner}/{repo}")

            # Use ghapi to get repository branches
            branches_data = client.repos.list_branches(owner, repo)

            branches = []
            for branch in branches_data:
                branches.append(
                    {
                        "name": branch.get("name"),
                        "protected": branch.get("protected", False),
                        "commit_sha": branch.get("commit", {}).get("sha"),
                        "commit_url": branch.get("commit", {}).get("url"),
                    }
                )

            return branches

        except Exception as e:
            logger.error(f"Error fetching repository branches for {owner}/{repo}: {e}")
            return []

    async def fetch_repository_contributors(
        self, owner: str, repo: str, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch repository contributors

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication
            limit: Maximum number of contributors to fetch

        Returns:
            List of repository contributors
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Fetching repository contributors for {owner}/{repo}")

            # Use ghapi to get repository contributors
            contributors_data = client.repos.list_contributors(
                owner, repo, per_page=limit, anon="false"
            )

            contributors = []
            for contributor in contributors_data[:limit]:
                contributors.append(
                    {
                        "login": contributor.get("login"),
                        "id": contributor.get("id"),
                        "avatar_url": contributor.get("avatar_url"),
                        "html_url": contributor.get("html_url"),
                        "contributions": contributor.get("contributions"),
                        "type": contributor.get("type"),
                    }
                )

            return contributors

        except Exception as e:
            logger.error(
                f"Error fetching repository contributors for {owner}/{repo}: {e}"
            )
            return []

    async def create_github_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        user_id: int,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub issue

        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue body
            user_id: User ID for authentication
            labels: Optional list of labels
            assignees: Optional list of assignees

        Returns:
            Created issue data or None if failed
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Creating GitHub issue in {owner}/{repo}: {title}")

            # Prepare issue data
            issue_data = {
                "title": title,
                "body": body,
            }

            if labels:
                issue_data["labels"] = labels

            if assignees:
                issue_data["assignees"] = assignees

            # Use ghapi to create the issue
            created_issue = client.issues.create(owner, repo, **issue_data)

            return {
                "id": created_issue.get("id"),
                "number": created_issue.get("number"),
                "html_url": created_issue.get("html_url"),
                "url": created_issue.get("url"),
                "title": created_issue.get("title"),
                "body": created_issue.get("body"),
                "state": created_issue.get("state"),
                "labels": [
                    label.get("name") for label in created_issue.get("labels", [])
                ],
                "assignees": [
                    assignee.get("login")
                    for assignee in created_issue.get("assignees", [])
                ],
                "created_at": created_issue.get("created_at"),
            }

        except Exception as e:
            logger.error(f"Error creating GitHub issue in {owner}/{repo}: {e}")
            return None

    async def update_github_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        user_id: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a GitHub issue

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            user_id: User ID for authentication
            title: Optional new title
            body: Optional new body
            state: Optional new state
            labels: Optional new labels
            assignees: Optional new assignees

        Returns:
            Updated issue data or None if failed
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Updating GitHub issue {owner}/{repo}#{issue_number}")

            # Prepare update data
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if body is not None:
                update_data["body"] = body
            if state is not None:
                update_data["state"] = state
            if labels is not None:
                update_data["labels"] = labels
            if assignees is not None:
                update_data["assignees"] = assignees

            if not update_data:
                logger.warning("No update data provided for issue update")
                return None

            # Use ghapi to update the issue
            updated_issue = client.issues.update(
                owner, repo, issue_number, **update_data
            )

            return {
                "id": updated_issue.get("id"),
                "number": updated_issue.get("number"),
                "html_url": updated_issue.get("html_url"),
                "title": updated_issue.get("title"),
                "body": updated_issue.get("body"),
                "state": updated_issue.get("state"),
                "labels": [
                    label.get("name") for label in updated_issue.get("labels", [])
                ],
                "assignees": [
                    assignee.get("login")
                    for assignee in updated_issue.get("assignees", [])
                ],
                "updated_at": updated_issue.get("updated_at"),
            }

        except Exception as e:
            logger.error(
                f"Error updating GitHub issue {owner}/{repo}#{issue_number}: {e}"
            )
            return None

    async def get_github_issue(
        self, owner: str, repo: str, issue_number: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a GitHub issue

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            user_id: User ID for authentication

        Returns:
            Issue data or None if not found
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Getting GitHub issue {owner}/{repo}#{issue_number}")

            # Use ghapi to get the issue
            issue = client.issues.get(owner, repo, issue_number)

            return {
                "id": issue.get("id"),
                "number": issue.get("number"),
                "html_url": issue.get("html_url"),
                "title": issue.get("title"),
                "body": issue.get("body"),
                "state": issue.get("state"),
                "labels": [label.get("name") for label in issue.get("labels", [])],
                "assignees": [
                    assignee.get("login") for assignee in issue.get("assignees", [])
                ],
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "closed_at": issue.get("closed_at"),
                "comments": issue.get("comments", 0),
                "user": {
                    "login": issue.get("user", {}).get("login"),
                    "avatar_url": issue.get("user", {}).get("avatar_url"),
                }
                if issue.get("user")
                else None,
            }

        except Exception as e:
            logger.error(
                f"Error getting GitHub issue {owner}/{repo}#{issue_number}: {e}"
            )
            return None

    async def add_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Add a comment to a GitHub issue

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment body
            user_id: User ID for authentication

        Returns:
            Created comment data or None if failed
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Adding comment to GitHub issue {owner}/{repo}#{issue_number}")

            # Use ghapi to create the comment
            comment = client.issues.create_comment(owner, repo, issue_number, body)

            return {
                "id": comment.get("id"),
                "html_url": comment.get("html_url"),
                "body": comment.get("body"),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "user": {
                    "login": comment.get("user", {}).get("login"),
                    "avatar_url": comment.get("user", {}).get("avatar_url"),
                }
                if comment.get("user")
                else None,
            }

        except Exception as e:
            logger.error(
                f"Error adding comment to GitHub issue {owner}/{repo}#{issue_number}: {e}"
            )
            return None

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
        user_id: int,
        draft: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub pull request

        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            head: Head branch
            base: Base branch
            body: PR body
            user_id: User ID for authentication
            draft: Whether to create as draft

        Returns:
            Created PR data or None if failed
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Creating pull request in {owner}/{repo}: {title}")

            # Use ghapi to create the pull request
            pr = client.pulls.create(owner, repo, title, head, base, body, draft=draft)

            return {
                "id": pr.get("id"),
                "number": pr.get("number"),
                "html_url": pr.get("html_url"),
                "title": pr.get("title"),
                "body": pr.get("body"),
                "state": pr.get("state"),
                "draft": pr.get("draft"),
                "head": {
                    "ref": pr.get("head", {}).get("ref"),
                    "sha": pr.get("head", {}).get("sha"),
                },
                "base": {
                    "ref": pr.get("base", {}).get("ref"),
                    "sha": pr.get("base", {}).get("sha"),
                },
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
            }

        except Exception as e:
            logger.error(f"Error creating pull request in {owner}/{repo}: {e}")
            return None

    async def get_repository_languages(
        self, owner: str, repo: str, user_id: int
    ) -> Dict[str, int]:
        """
        Get repository language statistics

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication

        Returns:
            Dictionary of languages and their byte counts
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Getting repository languages for {owner}/{repo}")

            # Use ghapi to get repository languages
            languages = client.repos.list_languages(owner, repo)

            return dict(languages) if languages else {}

        except Exception as e:
            logger.error(f"Error getting repository languages for {owner}/{repo}: {e}")
            return {}

    async def get_repository_readme(
        self, owner: str, repo: str, user_id: int, ref: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get repository README

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication
            ref: Optional branch/tag reference

        Returns:
            README data or None if not found
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Getting repository README for {owner}/{repo}")

            # Use ghapi to get repository README
            readme = client.repos.get_readme(owner, repo, ref=ref)

            return {
                "name": readme.get("name"),
                "path": readme.get("path"),
                "sha": readme.get("sha"),
                "size": readme.get("size"),
                "url": readme.get("url"),
                "html_url": readme.get("html_url"),
                "download_url": readme.get("download_url"),
                "content": readme.get("content"),
                "encoding": readme.get("encoding"),
            }

        except Exception as e:
            logger.error(f"Error getting repository README for {owner}/{repo}: {e}")
            return None

    async def list_repository_labels(
        self, owner: str, repo: str, user_id: int
    ) -> List[Dict[str, Any]]:
        """
        List repository labels

        Args:
            owner: Repository owner
            repo: Repository name
            user_id: User ID for authentication

        Returns:
            List of repository labels
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Listing repository labels for {owner}/{repo}")

            # Use ghapi to list repository labels
            labels = client.issues.list_labels_for_repo(owner, repo)

            return [
                {
                    "id": label.get("id"),
                    "name": label.get("name"),
                    "color": label.get("color"),
                    "description": label.get("description"),
                    "default": label.get("default"),
                }
                for label in labels
            ]

        except Exception as e:
            logger.error(f"Error listing repository labels for {owner}/{repo}: {e}")
            return []

    async def search_repositories(
        self,
        query: str,
        user_id: int,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Search for repositories

        Args:
            query: Search query
            user_id: User ID for authentication
            sort: Sort field
            order: Sort order
            per_page: Results per page

        Returns:
            List of repository search results
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Searching repositories with query: {query}")

            # Use ghapi to search repositories
            results = client.search.repos(
                query, sort=sort, order=order, per_page=per_page
            )

            repos = []
            for repo in results.get("items", []):
                repos.append(
                    {
                        "id": repo.get("id"),
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "owner": {
                            "login": repo.get("owner", {}).get("login"),
                            "avatar_url": repo.get("owner", {}).get("avatar_url"),
                        },
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "forks_count": repo.get("forks_count"),
                        "open_issues_count": repo.get("open_issues_count"),
                        "created_at": repo.get("created_at"),
                        "updated_at": repo.get("updated_at"),
                    }
                )

            return repos

        except Exception as e:
            logger.error(f"Error searching repositories with query '{query}': {e}")
            return []

    async def get_user_repositories(
        self,
        user_id: int,
        type_param: str = "owner",
        sort: str = "updated",
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get user's repositories

        Args:
            user_id: User ID for authentication
            type_param: Repository type filter
            sort: Sort field
            per_page: Results per page

        Returns:
            List of user's repositories
        """
        try:
            client = self.get_github_client(user_id)
            if not client:
                raise GitHubOpsError("No valid GitHub client available")

            logger.info(f"Getting repositories for user {user_id}")

            # Use ghapi to list user repositories
            repos = client.repos.list_for_authenticated_user(
                type=type_param, sort=sort, per_page=per_page
            )

            repositories = []
            for repo in repos:
                repositories.append(
                    {
                        "id": repo.get("id"),
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "owner": {
                            "login": repo.get("owner", {}).get("login"),
                            "avatar_url": repo.get("owner", {}).get("avatar_url"),
                        },
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "forks_count": repo.get("forks_count"),
                        "open_issues_count": repo.get("open_issues_count"),
                        "private": repo.get("private"),
                        "archived": repo.get("archived"),
                        "created_at": repo.get("created_at"),
                        "updated_at": repo.get("updated_at"),
                        "pushed_at": repo.get("pushed_at"),
                    }
                )

            return repositories

        except Exception as e:
            logger.error(f"Error getting repositories for user {user_id}: {e}")
            return []
