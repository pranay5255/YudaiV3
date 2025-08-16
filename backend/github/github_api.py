#!/usr/bin/env python3
"""
GitHub API Integration Module

This module provides additional GitHub API functionality using ghapi
for authenticated users, including repository management, issues, and more.
"""

from typing import List, Optional

from auth.github_oauth import get_github_api
from ghapi import GhApi
from models import (
    Commit,
    GitHubBranch,
    GitHubCommit,
    GitHubIssue,
    GitHubPullRequest,
    GitHubRepo,
    GitHubSearchResponse,
    Issue,
    PullRequest,
    Repository,
    User,
)
from sqlalchemy.orm import Session


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors"""
    pass

async def get_user_repositories(
    current_user: User,
    db: Session
) -> List[GitHubRepo]:
    """
    Get all repositories for the authenticated user from GitHub,
    update the database only if repository doesn't exist, and return the list.
    """
    try:
        # Get GitHub API client - this handles authentication properly
        api = get_github_api(current_user.id, db)
        
        # Fetch repositories from GitHub API
        try:    
            repos_data = api.repos.list_for_authenticated_user(sort="updated", per_page=100)
            
            # Handle case where repos_data might not be iterable
            if not hasattr(repos_data, '__iter__'):
                print(f"Unexpected repos_data type: {type(repos_data)}")
                return []
                
        except Exception as api_error:
            print(f"GitHub API error: {str(api_error)}")
            raise GitHubAPIError(f"Failed to fetch repositories from GitHub: {str(api_error)}")
        
        for repo_data in repos_data:
            try:
                # Check if repository already exists in database
                existing_repo = db.query(Repository).filter(Repository.github_repo_id == repo_data.id).first()
                
                if not existing_repo:
                    # Only create new repository if it doesn't exist
                    repo = Repository(github_repo_id=repo_data.id, user_id=current_user.id)
                    db.add(repo)
                    
                    # Set all the fields for new repository with safe access
                    repo.name = getattr(repo_data, 'name', None)
                    repo.owner = getattr(repo_data.owner, 'login', None) if hasattr(repo_data, 'owner') and repo_data.owner else None
                    repo.full_name = getattr(repo_data, 'full_name', None)
                    repo.description = getattr(repo_data, 'description', None)
                    repo.private = getattr(repo_data, 'private', False)
                    repo.html_url = getattr(repo_data, 'html_url', None)
                    repo.clone_url = getattr(repo_data, 'clone_url', None)
                    repo.language = getattr(repo_data, 'language', None)
                    repo.stargazers_count = getattr(repo_data, 'stargazers_count', 0)
                    repo.forks_count = getattr(repo_data, 'forks_count', 0)
                    repo.open_issues_count = getattr(repo_data, 'open_issues_count', 0)
                    repo.default_branch = getattr(repo_data, 'default_branch', None)
                    repo.github_created_at = getattr(repo_data, 'created_at', None)
                    repo.github_updated_at = getattr(repo_data, 'updated_at', None)
                    repo.pushed_at = getattr(repo_data, 'pushed_at', None)
            except Exception as repo_error:
                print(f"Error processing repository {getattr(repo_data, 'name', 'unknown')}: {str(repo_error)}")
                continue

        db.commit()
        return [GitHubRepo.model_validate(r) for r in repos_data]

    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        print(f"Error in get_user_repositories: {str(e)}")
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch repositories: {str(e)}")

async def get_repository_details(
    owner: str,
    repo_name: str,
    current_user: User,
    db: Session
) -> GitHubRepo:
    """
    Get detailed information for a repository, update the database only if repository doesn't exist, and return it.
    """
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        repo_data = api.repos.get(owner=owner, repo=repo_name)
        
        if not repo_data:
            raise GitHubAPIError(f"Repository {owner}/{repo_name} not found")
        
        # Check if repository already exists in database
        existing_repo = db.query(Repository).filter(Repository.github_repo_id == repo_data.id).first()
        
        if not existing_repo:
            # Only create new repository if it doesn't exist
            repo = Repository(github_repo_id=repo_data.id, user_id=current_user.id)
            db.add(repo)
            
            # Set all the fields for new repository with safe access
            repo.name = getattr(repo_data, 'name', None)
            repo.owner = getattr(repo_data.owner, 'login', None) if hasattr(repo_data, 'owner') and repo_data.owner else None
            repo.full_name = getattr(repo_data, 'full_name', None)
            repo.description = getattr(repo_data, 'description', None)
            repo.private = getattr(repo_data, 'private', False)
            repo.html_url = getattr(repo_data, 'html_url', None)
            repo.clone_url = getattr(repo_data, 'clone_url', None)
            repo.language = getattr(repo_data, 'language', None)
            repo.stargazers_count = getattr(repo_data, 'stargazers_count', 0)
            repo.forks_count = getattr(repo_data, 'forks_count', 0)
            repo.open_issues_count = getattr(repo_data, 'open_issues_count', 0)
            repo.default_branch = getattr(repo_data, 'default_branch', None)
            repo.github_created_at = getattr(repo_data, 'created_at', None)
            repo.github_updated_at = getattr(repo_data, 'updated_at', None)
            repo.pushed_at = getattr(repo_data, 'pushed_at', None)
            
            db.commit()
        
        return GitHubRepo.model_validate(repo_data)

    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch repository details: {str(e)}")


async def create_issue(
    owner: str,
    repo_name: str,
    title: str,
    body: str,
    current_user: User,
    db: Session,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None
) -> GitHubIssue:
    """
    Create a new issue, save it to the database only if it doesn't exist, and return it.
    """
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        issue_data = api.issues.create(
            owner=owner, repo=repo_name, title=title, body=body,
            labels=labels or [], assignees=assignees or []
        )
        
        if not issue_data:
            raise GitHubAPIError("Failed to create issue - no data returned")
        
        # Check if issue already exists in database
        existing_issue = db.query(Issue).filter(Issue.github_issue_id == issue_data.id).first()
        
        if not existing_issue:
            repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
            if repo:
                new_issue = Issue(
                    github_issue_id=getattr(issue_data, 'id', None),
                    repository_id=repo.id,
                    number=getattr(issue_data, 'number', None),
                    title=getattr(issue_data, 'title', title),
                    body=getattr(issue_data, 'body', body),
                    state=getattr(issue_data, 'state', 'open'),
                    html_url=getattr(issue_data, 'html_url', None),
                    author_username=getattr(issue_data.user, 'login', None) if hasattr(issue_data, 'user') and issue_data.user else None,
                    github_created_at=getattr(issue_data, 'created_at', None),
                    github_updated_at=getattr(issue_data, 'updated_at', None)
                )
                db.add(new_issue)
                db.commit()
            
        return GitHubIssue.model_validate(issue_data)

    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to create issue: {str(e)}")

async def get_repository_issues(
    owner: str,
    repo_name: str,
    state: str,
    current_user: User,
    db: Session
) -> List[GitHubIssue]:
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        issues_data = api.issues.list_for_repo(owner=owner, repo=repo_name, state=state, per_page=100)
        
        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")
            
        # Handle case where issues_data might not be iterable
        if not hasattr(issues_data, '__iter__'):
            print(f"Unexpected issues_data type: {type(issues_data)}")
            return []
            
        for issue_data in issues_data:
            try:
                # Check if issue already exists in database
                existing_issue = db.query(Issue).filter(Issue.github_issue_id == issue_data.id).first()
                
                if not existing_issue:
                    # Only create new issue if it doesn't exist
                    issue = Issue(github_issue_id=getattr(issue_data, 'id', None), repository_id=repo.id)
                    db.add(issue)
                    
                    # Set all the fields for new issue with safe access
                    issue.number = getattr(issue_data, 'number', None)
                    issue.title = getattr(issue_data, 'title', None)
                    issue.body = getattr(issue_data, 'body', None)
                    issue.state = getattr(issue_data, 'state', None)
                    issue.html_url = getattr(issue_data, 'html_url', None)
                    issue.author_username = getattr(issue_data.user, 'login', None) if hasattr(issue_data, 'user') and issue_data.user else None
                    issue.github_created_at = getattr(issue_data, 'created_at', None)
                    issue.github_updated_at = getattr(issue_data, 'updated_at', None)
                    issue.github_closed_at = getattr(issue_data, 'closed_at', None)
            except Exception as issue_error:
                print(f"Error processing issue {getattr(issue_data, 'number', 'unknown')}: {str(issue_error)}")
                continue
        
        db.commit()
        return [GitHubIssue.model_validate(i) for i in issues_data]
    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch issues: {str(e)}")


async def get_repository_pulls(
    owner: str,
    repo_name: str,
    state: str,
    current_user: User,
    db: Session
) -> List[GitHubPullRequest]:
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        pulls_data = api.pulls.list(owner=owner, repo=repo_name, state=state, per_page=100)

        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")

        # Handle case where pulls_data might not be iterable
        if not hasattr(pulls_data, '__iter__'):
            print(f"Unexpected pulls_data type: {type(pulls_data)}")
            return []

        for pr_data in pulls_data:
            try:
                # Check if pull request already exists in database
                existing_pr = db.query(PullRequest).filter(PullRequest.github_pr_id == pr_data.id).first()
                
                if not existing_pr:
                    # Only create new pull request if it doesn't exist
                    pr = PullRequest(github_pr_id=getattr(pr_data, 'id', None), repository_id=repo.id)
                    db.add(pr)
                    
                    # Set all the fields for new pull request with safe access
                    pr.number = getattr(pr_data, 'number', None)
                    pr.title = getattr(pr_data, 'title', None)
                    pr.body = getattr(pr_data, 'body', None)
                    pr.state = getattr(pr_data, 'state', None)
                    pr.html_url = getattr(pr_data, 'html_url', None)
                    pr.author_username = getattr(pr_data.user, 'login', None) if hasattr(pr_data, 'user') and pr_data.user else None
                    pr.github_created_at = getattr(pr_data, 'created_at', None)
                    pr.github_updated_at = getattr(pr_data, 'updated_at', None)
                    pr.github_closed_at = getattr(pr_data, 'closed_at', None)
                    pr.merged_at = getattr(pr_data, 'merged_at', None)
            except Exception as pr_error:
                print(f"Error processing pull request {getattr(pr_data, 'number', 'unknown')}: {str(pr_error)}")
                continue

        db.commit()
        return [GitHubPullRequest.model_validate(p) for p in pulls_data]
    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch pull requests: {str(e)}")


async def get_repository_commits(
    owner: str,
    repo_name: str,
    branch: str,
    current_user: User,
    db: Session
) -> List[GitHubCommit]:
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        commits_data = api.repos.list_commits(owner=owner, repo=repo_name, sha=branch, per_page=100)

        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")

        # Handle case where commits_data might not be iterable
        if not hasattr(commits_data, '__iter__'):
            print(f"Unexpected commits_data type: {type(commits_data)}")
            return []

        for commit_data in commits_data:
            try:
                # Check if commit already exists in database
                existing_commit = db.query(Commit).filter(Commit.sha == getattr(commit_data, 'sha', None)).first()
                
                if not existing_commit and getattr(commit_data, 'sha', None):
                    # Only create new commit if it doesn't exist
                    commit = Commit(sha=commit_data.sha, repository_id=repo.id)
                    db.add(commit)
                    
                    # Set all the fields for new commit with safe access
                    commit.message = getattr(commit_data.commit, 'message', None) if hasattr(commit_data, 'commit') and commit_data.commit else None
                    commit.html_url = getattr(commit_data, 'html_url', None)
                    
                    if hasattr(commit_data, 'commit') and commit_data.commit and hasattr(commit_data.commit, 'author') and commit_data.commit.author:
                        commit.author_name = getattr(commit_data.commit.author, 'name', None)
                        commit.author_email = getattr(commit_data.commit.author, 'email', None)
                        commit.author_date = getattr(commit_data.commit.author, 'date', None)
            except Exception as commit_error:
                print(f"Error processing commit {getattr(commit_data, 'sha', 'unknown')}: {str(commit_error)}")
                continue

        db.commit()
        return [GitHubCommit.model_validate(c) for c in commits_data]
    except GitHubAPIError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch commits: {str(e)}")


async def get_repository_branches(
    owner: str,
    repo_name: str,
    current_user: User,
    db: Session
) -> List[GitHubBranch]:
    """
    Get branches for a repository
    """
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        branches_data = api.repos.list_branches(owner=owner, repo=repo_name, per_page=100)
        
        # Handle case where branches_data might not be iterable
        if not hasattr(branches_data, '__iter__'):
            print(f"Unexpected branches_data type: {type(branches_data)}")
            return []
        
        return [GitHubBranch.model_validate(branch) for branch in branches_data]
    except GitHubAPIError:
        raise
    except Exception as e:
        raise GitHubAPIError(f"Failed to fetch branches: {str(e)}")


async def search_repositories(
    query: str,
    current_user: User,
    db: Session,
    sort: str = "stars",
    order: str = "desc"
) -> GitHubSearchResponse:
    """
    Search repositories on GitHub. This function will not save to DB
    as search results are transient.
    """
    try:
        api = get_github_api(current_user.id, db)
        
        if GhApi is None:
            raise GitHubAPIError("GitHub API library not available")
            
        results = api.search.repos(q=query, sort=sort, order=order, per_page=30)
        
        if not results:
            raise GitHubAPIError("No search results returned")
            
        return GitHubSearchResponse.model_validate(results)
    except GitHubAPIError:
        raise
    except Exception as e:
        raise GitHubAPIError(f"Failed to search repositories: {str(e)}")