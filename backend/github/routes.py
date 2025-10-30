#!/usr/bin/env python3
"""
GitHub integration routes

Provides endpoints for:
- Listing authenticated user's repositories
- Listing branches for a repository

Backed by daifuUserAgent.githubOps.GitHubOps using the logged-in user's token.
"""

from typing import List

from auth.github_oauth import get_current_user
from daifuUserAgent.githubOps import GitHubOps
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import User
from sqlalchemy.orm import Session

router = APIRouter(tags=["github"])


@router.get("/repositories", response_model=List[dict])
async def list_user_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List repositories accessible by the authenticated user using their GitHub token.
    """
    try:
        ops = GitHubOps(db)
        repos = await ops.get_user_repositories(user_id=current_user.id)
        return repos
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch repositories: {str(e)}",
        )


@router.get("/repositories/{owner}/{repo}/branches", response_model=List[dict])
async def list_repository_branches(
    owner: str,
    repo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List branches for a specific repository the authenticated user can access.
    """
    try:
        ops = GitHubOps(db)
        branches = await ops.fetch_repository_branches(owner, repo, current_user.id)
        # Normalize shape to include name and commit object for frontend types
        normalized = [
            {
                "name": b.get("name"),
                "protected": bool(b.get("protected", False)),
                "commit": {
                    "sha": b.get("commit_sha"),
                    "url": b.get("commit_url"),
                },
            }
            for b in branches
        ]
        return normalized
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch branches: {str(e)}",
        )


