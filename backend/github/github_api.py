#!/usr/bin/env python3
"""
GitHub API Integration Module

This module provides additional GitHub API functionality using ghapi
for authenticated users, including repository management, issues, and more.
"""

from typing import List, Optional
from fastapi import Depends
from sqlalchemy.orm import Session, joinedload
from ghapi.all import GhApi

from db.database import get_db
from models import (
    User, 
    Repository,
    Issue,
    PullRequest,
    Commit,
    GitHubRepo, 
    GitHubIssue, 
    GitHubPullRequest, 
    GitHubCommit, 
    GitHubSearchResponse
)
from auth.github_oauth import get_github_api, get_current_user

class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors"""
    pass

async def get_user_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[GitHubRepo]:
    """
    Get all repositories for the authenticated user from GitHub,
    update the database, and return the list.
    """
    try:
        api = get_github_api(current_user.id, db)
        repos_data = api.repos.list_for_authenticated_user(sort="updated", per_page=100)
        
        for repo_data in repos_data:
            repo = db.query(Repository).filter(Repository.github_repo_id == repo_data.id).first()
            if not repo:
                repo = Repository(github_repo_id=repo_data.id, user_id=current_user.id)
                db.add(repo)
            
            repo.name = repo_data.name
            repo.owner = repo_data.owner.login
            repo.full_name = repo_data.full_name
            repo.description = repo_data.description
            repo.private = repo_data.private
            repo.html_url = repo_data.html_url
            repo.clone_url = repo_data.clone_url
            repo.language = repo_data.language
            repo.stargazers_count = repo_data.stargazers_count
            repo.forks_count = repo_data.forks_count
            repo.open_issues_count = repo_data.open_issues_count
            repo.github_created_at = repo_data.created_at
            repo.github_updated_at = repo_data.updated_at
            repo.pushed_at = repo_data.pushed_at

        db.commit()
        return [GitHubRepo.model_validate(r) for r in repos_data]

    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch repositories: {str(e)}")

async def get_repository_details(
    owner: str,
    repo_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> GitHubRepo:
    """
    Get detailed information for a repository, update the database, and return it.
    """
    try:
        api = get_github_api(current_user.id, db)
        repo_data = api.repos.get(owner=owner, repo=repo_name)
        
        repo = db.query(Repository).filter(Repository.github_repo_id == repo_data.id).first()
        if not repo:
            repo = Repository(github_repo_id=repo_data.id, user_id=current_user.id)
            db.add(repo)
        
        # Update fields...
        repo.name = repo_data.name
        repo.owner = repo_data.owner.login
        repo.full_name = repo_data.full_name
        repo.description = repo_data.description
        repo.private = repo_data.private
        repo.html_url = repo_data.html_url
        repo.clone_url = repo_data.clone_url
        repo.language = repo_data.language
        repo.stargazers_count = repo_data.stargazers_count
        repo.forks_count = repo_data.forks_count
        repo.open_issues_count = repo_data.open_issues_count
        repo.github_created_at = repo_data.created_at
        repo.github_updated_at = repo_data.updated_at
        repo.pushed_at = repo_data.pushed_at
        
        db.commit()
        return GitHubRepo.model_validate(repo_data)

    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch repository details: {str(e)}")


async def create_issue(
    owner: str,
    repo_name: str,
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> GitHubIssue:
    """
    Create a new issue, save it to the database, and return it.
    """
    try:
        api = get_github_api(current_user.id, db)
        issue_data = api.issues.create(
            owner=owner, repo=repo_name, title=title, body=body,
            labels=labels or [], assignees=assignees or []
        )
        
        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if repo:
            new_issue = Issue(
                github_issue_id=issue_data.id,
                repository_id=repo.id,
                number=issue_data.number,
                title=issue_data.title,
                body=issue_data.body,
                state=issue_data.state,
                html_url=issue_data.html_url,
                author_username=issue_data.user.login,
                github_created_at=issue_data.created_at,
                github_updated_at=issue_data.updated_at
            )
            db.add(new_issue)
            db.commit()
            
        return GitHubIssue.model_validate(issue_data)

    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to create issue: {str(e)}")

async def get_repository_issues(
    owner: str,
    repo_name: str,
    state: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[GitHubIssue]:
    try:
        api = get_github_api(current_user.id, db)
        issues_data = api.issues.list_for_repo(owner=owner, repo=repo_name, state=state, per_page=100)
        
        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")
            
        for issue_data in issues_data:
            issue = db.query(Issue).filter(Issue.github_issue_id == issue_data.id).first()
            if not issue:
                issue = Issue(github_issue_id=issue_data.id, repository_id=repo.id)
                db.add(issue)
            
            issue.number = issue_data.number
            issue.title = issue_data.title
            issue.body = issue_data.body
            issue.state = issue_data.state
            issue.html_url = issue_data.html_url
            issue.author_username = issue_data.user.login if issue_data.user else None
            issue.github_created_at = issue_data.created_at
            issue.github_updated_at = issue_data.updated_at
            issue.github_closed_at = issue_data.closed_at
        
        db.commit()
        return [GitHubIssue.model_validate(i) for i in issues_data]
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
        pulls_data = api.pulls.list(owner=owner, repo=repo_name, state=state, per_page=100)

        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")

        for pr_data in pulls_data:
            pr = db.query(PullRequest).filter(PullRequest.github_pr_id == pr_data.id).first()
            if not pr:
                pr = PullRequest(github_pr_id=pr_data.id, repository_id=repo.id)
                db.add(pr)

            pr.number = pr_data.number
            pr.title = pr_data.title
            pr.body = pr_data.body
            pr.state = pr_data.state
            pr.html_url = pr_data.html_url
            pr.author_username = pr_data.user.login if pr_data.user else None
            pr.github_created_at = pr_data.created_at
            pr.github_updated_at = pr_data.updated_at
            pr.github_closed_at = pr_data.closed_at
            pr.merged_at = pr_data.merged_at

        db.commit()
        return [GitHubPullRequest.model_validate(p) for p in pulls_data]
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
        commits_data = api.repos.list_commits(owner=owner, repo=repo_name, sha=branch, per_page=100)

        repo = db.query(Repository).filter(Repository.full_name == f"{owner}/{repo_name}").first()
        if not repo:
            raise GitHubAPIError("Repository not found in database.")

        for commit_data in commits_data:
            commit = db.query(Commit).filter(Commit.sha == commit_data.sha).first()
            if not commit:
                commit = Commit(sha=commit_data.sha, repository_id=repo.id)
                db.add(commit)

            commit.message = commit_data.commit.message
            commit.html_url = commit_data.html_url
            if commit_data.author:
                commit.author_name = commit_data.commit.author.name
                commit.author_email = commit_data.commit.author.email
                commit.author_date = commit_data.commit.author.date

        db.commit()
        return [GitHubCommit.model_validate(c) for c in commits_data]
    except Exception as e:
        db.rollback()
        raise GitHubAPIError(f"Failed to fetch commits: {str(e)}")


async def search_repositories(
    query: str,
    sort: str = "stars",
    order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> GitHubSearchResponse:
    """
    Search repositories on GitHub. This function will not save to DB
    as search results are transient.
    """
    try:
        api = get_github_api(current_user.id, db)
        results = api.search.repos(q=query, sort=sort, order=order, per_page=30)
        return GitHubSearchResponse.model_validate(results)
    except Exception as e:
        raise GitHubAPIError(f"Failed to search repositories: {str(e)}") 