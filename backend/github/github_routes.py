 #!/usr/bin/env python3
"""
GitHub API Routes

This module provides FastAPI routes for GitHub API functionality,
including repository management, issues, and search.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from db.database import get_db
from models import (
    User,
    CreateIssueRequest,
    GitHubRepo,
    GitHubIssue,
    GitHubPullRequest,
    GitHubCommit,
    GitHubSearchResponse,
)
from .github_api import (
    get_user_repositories,
    get_repository_details,
    create_issue,
    get_repository_issues,
    get_repository_pulls,
    get_repository_commits,
    search_repositories,
    GitHubAPIError
)
from auth.github_oauth import get_current_user

router = APIRouter(prefix="/github", tags=["github"])

@router.get("/repositories", response_model=List[GitHubRepo])
async def get_my_repositories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all repositories for the authenticated user from GitHub
    """
    try:
        return await get_user_repositories(current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/repositories/{owner}/{repo}", response_model=GitHubRepo)
async def get_repository_info(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific repository
    """
    try:
        return await get_repository_details(owner, repo, current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/repositories/{owner}/{repo}/issues", response_model=GitHubIssue)
async def create_repository_issue(
    owner: str,
    repo: str,
    request: CreateIssueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new issue in a repository
    """
    try:
        return await create_issue(
            owner=owner,
            repo=repo,
            title=request.title,
            body=request.description,
            labels=getattr(request, "labels", None),
            assignees=getattr(request, "assignees", None),
            current_user=current_user,
            db=db
        )
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/repositories/{owner}/{repo}/issues", response_model=List[GitHubIssue])
async def get_repository_issues_list(
    owner: str,
    repo: str,
    state: str = Query("open", description="Issue state: open, closed, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get issues for a repository
    """
    try:
        return await get_repository_issues(owner, repo, state, current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/repositories/{owner}/{repo}/pulls", response_model=List[GitHubPullRequest])
async def get_repository_pulls_list(
    owner: str,
    repo: str,
    state: str = Query("open", description="PR state: open, closed, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pull requests for a repository
    """
    try:
        return await get_repository_pulls(owner, repo, state, current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/repositories/{owner}/{repo}/commits", response_model=List[GitHubCommit])
async def get_repository_commits_list(
    owner: str,
    repo: str,
    branch: str = Query("main", description="Branch name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get commits for a repository branch
    """
    try:
        return await get_repository_commits(owner, repo, branch, current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/search/repositories", response_model=GitHubSearchResponse)
async def search_github_repositories(
    q: str = Query(..., description="Search query"),
    sort: str = Query("stars", description="Sort field: stars, forks, help-wanted-issues, updated"),
    order: str = Query("desc", description="Sort order: desc, asc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search repositories on GitHub
    """
    try:
        return await search_repositories(q, sort, order, current_user, db)
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )