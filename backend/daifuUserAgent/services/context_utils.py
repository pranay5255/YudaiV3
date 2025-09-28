#!/usr/bin/env python3
"""
Context Utilities - Shared helpers for repository context fetching, caching and formatting.

This module consolidates duplicated logic from ChatOps and IssueOps for:
- Fetching comprehensive GitHub repository context using GitHubOps
- Reading/writing cached repository context via LLMService
- Selecting the best available repository context with graceful fallbacks
- Formatting repository context to a concise string
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)


def _build_context_string(
    repo_info: Dict[str, Any], issues: List[Dict[str, Any]], commits: List[Dict[str, Any]]
) -> str:
    """Build a concise context string from repository metadata."""
    context_parts: List[str] = []

    if repo_info.get("name"):
        owner_login = (
            repo_info.get("owner", {}).get("login") if isinstance(repo_info.get("owner"), dict) else None
        )
        full_name = repo_info.get("full_name") or (
            f"{owner_login}/{repo_info['name']}" if owner_login and repo_info.get("name") else repo_info.get("name")
        )
        context_parts.append(f"Repository: {full_name}")
        if repo_info.get("description"):
            context_parts.append(f"Description: {repo_info['description']}")
        if repo_info.get("language"):
            context_parts.append(f"Language: {repo_info['language']}")
        if repo_info.get("topics"):
            topics = repo_info.get("topics") or []
            if isinstance(topics, list) and topics:
                context_parts.append(f"Topics: {', '.join(topics[:5])}")

    if issues:
        context_parts.append(f"\nRecent Issues ({len(issues)}):")
        for issue in issues[:3]:
            try:
                context_parts.append(f"- #{issue.get('number')}: {issue.get('title')}")
            except Exception:
                continue

    if commits:
        context_parts.append(f"\nRecent Commits ({len(commits)}):")
        for commit in commits[:3]:
            try:
                sha = commit.get("sha") or commit.get("id")
                message = commit.get("message") or commit.get("commit", {}).get("message")
                if sha and message:
                    context_parts.append(f"- {sha}: {message}")
            except Exception:
                continue

    return "\n".join(context_parts) if context_parts else "Repository context not available"


async def fetch_comprehensive_github_context(
    db: Session, repo_owner: str, repo_name: str, user_id: int
) -> Dict[str, Any]:
    """Fetch rich repository context via GitHubOps, combining metadata, branches, contributors, issues, commits."""
    from ..githubOps import GitHubOps

    github_ops = GitHubOps(db)

    repo_data = await github_ops.fetch_repository_info_detailed(repo_owner, repo_name, user_id)
    branches = await github_ops.fetch_repository_branches(repo_owner, repo_name, user_id)
    contributors = await github_ops.fetch_repository_contributors(repo_owner, repo_name, user_id, limit=10)
    issues_data = await github_ops.fetch_repository_issues(repo_owner, repo_name, user_id, limit=5)
    commits_data = await github_ops.fetch_repository_commits(repo_owner, repo_name, user_id, limit=5)

    # Basic info for concise context string
    basic_repo_info = await github_ops.fetch_repository_info(repo_owner, repo_name, user_id)
    context_string = _build_context_string(basic_repo_info or {}, issues_data or [], commits_data or [])

    return {
        "repository": repo_data,
        "branches": branches,
        "contributors": contributors,
        "recent_issues": issues_data,
        "recent_commits": commits_data,
        "context_string": context_string,
        "fetched_at": utc_now().isoformat(),
        "owner": repo_owner,
        "name": repo_name,
    }


def format_github_context_from_cache(cached: dict) -> str:
    """Format repository context from cached JSON structure."""
    try:
        parts: List[str] = []

        repo_info = cached.get("repository", {}) if isinstance(cached, dict) else {}
        if repo_info:
            owner_login = repo_info.get("owner", {}).get("login") if isinstance(repo_info.get("owner"), dict) else None
            full_name = repo_info.get("full_name") or (
                f"{owner_login}/{repo_info.get('name')}" if owner_login and repo_info.get("name") else repo_info.get("name")
            )
            if full_name:
                parts.append(f"Repository: {full_name}")
            description = repo_info.get("description")
            if description:
                parts.append(f"Description: {description}")
            language = repo_info.get("language")
            if language:
                parts.append(f"Language: {language}")

        issues = cached.get("recent_issues") or cached.get("issues") or []
        if isinstance(issues, list) and issues:
            parts.append("\nRecent Open Issues:")
            for issue in issues[:3]:
                if isinstance(issue, dict):
                    number = issue.get("number", "N/A")
                    title = issue.get("title", "No title")
                    parts.append(f"- #{number}: {title}")

        commits = cached.get("recent_commits") or cached.get("commits") or []
        if isinstance(commits, list) and commits:
            parts.append("\nRecent Commits:")
            for commit in commits[:3]:
                message = commit.get("commit", {}).get("message") or commit.get("message") or "No message"
                author = commit.get("commit", {}).get("author", {}).get("name") or commit.get("author", {}).get("login") or "Unknown"
                parts.append(f"- {message[:100]}... (by {author})")

        return "\n".join(parts) if parts else "Repository context available"
    except Exception as e:
        logger.error(f"Failed to format cached GitHub context: {e}")
        return "Repository context available (parsing failed)"


async def ensure_github_context(
    db: Session, user_id: int, session_obj, repo_owner: str, repo_name: str
) -> Optional[dict]:
    """
    Ensure repository context is available and fresh:
    - Try DB metadata (Repository.github_context) -> read cached JSON
    - If stale or missing -> fetch via GitHubOps and write cache; persist metadata
    - Return cached JSON structure
    """
    from models import Repository

    from ..llm_service import LLMService

    github_context: Optional[dict] = None

    try:
        repository = (
            db.query(Repository)
            .filter(
                Repository.owner == repo_owner,
                Repository.name == repo_name,
                Repository.user_id == user_id,
            )
            .first()
        )

        # Try to load from existing cache metadata if fresh (<24h)
        if (
            repository
            and getattr(repository, "github_context", None)
            and getattr(repository, "github_context_updated_at", None)
        ):
            try:
                age_seconds = (utc_now() - repository.github_context_updated_at).total_seconds()
                if age_seconds < 86400:
                    github_context = LLMService.read_github_context_cache(repository.github_context)
                    if github_context:
                        return github_context
                else:
                    logger.info(
                        f"GitHub context for {repo_owner}/{repo_name} is stale ({int(age_seconds)}s old); refreshing"
                    )
            except Exception as e:
                logger.debug(f"Failed to read existing GitHub context cache: {e}")

        # Fetch fresh and write to cache
        fetched_context = await fetch_comprehensive_github_context(db, repo_owner, repo_name, user_id)
        if fetched_context:
            cache_meta = LLMService.write_github_context_cache(
                data=fetched_context,
                user_id=user_id,
                session_id=getattr(session_obj, "session_id", None) or "session",
                owner=repo_owner,
                name=repo_name,
            )

            # Persist cache metadata on Repository row (create or update)
            if not repository:
                repository = Repository(
                    user_id=user_id,
                    name=repo_name,
                    owner=repo_owner,
                    full_name=f"{repo_owner}/{repo_name}",
                    repo_url=f"https://github.com/{repo_owner}/{repo_name}",
                    html_url=f"https://github.com/{repo_owner}/{repo_name}",
                    clone_url=f"https://github.com/{repo_owner}/{repo_name}.git",
                    github_context=cache_meta,
                    github_context_updated_at=utc_now(),
                )
                db.add(repository)
            else:
                repository.github_context = cache_meta
                repository.github_context_updated_at = utc_now()

            try:
                db.commit()
            except Exception as commit_err:
                logger.warning(f"Failed to commit Repository metadata update: {commit_err}")
                db.rollback()

            try:
                github_context = LLMService.read_github_context_cache(cache_meta)
            except Exception as e:
                logger.debug(f"Failed to read back freshly written context cache: {e}")

        return github_context

    except Exception as e:
        logger.warning(f"ensure_github_context failed: {e}")
        return None


async def get_best_repo_context_string(
    db: Session, user_id: int, session_id: str, repo_owner: str, repo_name: str
) -> str:
    """
    Return the best available string-form repository context with fallbacks:
    1) DB -> read cached JSON and format
    2) LLMService cache path
    3) GitIngest repository summary
    4) Minimal fallback
    """
    from models import Repository

    from ..llm_service import LLMService

    try:
        # Try DB metadata first
        repository = (
            db.query(Repository)
            .filter(
                Repository.owner == repo_owner,
                Repository.name == repo_name,
                Repository.user_id == user_id,
            )
            .first()
        )

        if repository and getattr(repository, "github_context", None):
            try:
                cached = LLMService.read_github_context_cache(repository.github_context)
                if cached:
                    return format_github_context_from_cache(cached)
            except Exception as e:
                logger.debug(f"Failed reading DB-backed cache: {e}")

        # Try LLMService cache path derived from inputs
        try:
            cache_meta = {
                "cache_path": LLMService.cache_path_for_repo(user_id, session_id, repo_owner, repo_name),
                "user_id": user_id,
                "session_id": session_id,
                "owner": repo_owner,
                "name": repo_name,
            }
            cached = LLMService.read_github_context_cache(cache_meta)
            if cached:
                return format_github_context_from_cache(cached)
        except Exception as e:
            logger.debug(f"Failed reading derived cache path: {e}")

        # Fallback to GitIngest (best-effort)
        fallback = await get_gitingest_repo_context(repo_owner, repo_name)
        if fallback:
            return fallback

        return f"Repository: {repo_owner}/{repo_name}"
    except Exception as e:
        logger.error(f"get_best_repo_context_string failed: {e}")
        return f"Repository: {repo_owner}/{repo_name}"


async def get_gitingest_repo_context(repo_owner: str, repo_name: str) -> Optional[str]:
    """Use GitIngest-based scraper to produce a lightweight summary string."""
    try:
        from ..repo_processorGitIngest.scraper_script import extract_repository_data

        repo_url = f"https://github.com/{repo_owner}/{repo_name}"
        repo_data = await extract_repository_data(repo_url)

        if not repo_data or "raw_response" not in repo_data:
            return None

        parts: List[str] = [f"Repository: {repo_owner}/{repo_name}"]
        raw_response = repo_data.get("raw_response", {})

        summary = raw_response.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary[:500]}...")

        tree = raw_response.get("tree", "")
        if tree:
            lines = tree.strip().split("\n")
            dirs = [line for line in lines if line.strip().endswith("/")]
            if dirs:
                parts.append(f"\nDirectory Structure ({len(dirs)} directories):")
                for dir_name in dirs[:10]:
                    parts.append(f"- {dir_name.strip()}")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"GitIngest fallback failed: {e}")
        return None


