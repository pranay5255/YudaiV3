"""
Async video generation for PR explainer videos.

This module defines the interface for generating short (10-15s) explainer videos
that visualize the changes made by the solver agent. Videos are uploaded as
comments to the PR after creation.

The actual rendering implementation is deferred — this module currently contains
only the interface stub and kickoff mechanism.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def kick_off_video_generation(
    *,
    pr_url: str,
    repo_url: str,
    issue_url: str,
    branch_name: str,
    github_token: str,
    solve_id: str,
    run_id: str,
) -> None:
    """
    Placeholder for async video generation.

    Future implementation will:
    1. Spawn a separate Modal sandbox with SOLVER_VIDEO_IMAGE (manim + ffmpeg)
    2. Clone the repo at branch_name, run `git diff main..HEAD`
    3. Generate mermaid diagram of touched modules (from import graph)
    4. Select ~20% of diff hunks as representative code changes
    5. Render 10-15s Manim video:
       - Scene 1 (5-7s): Mermaid-style architecture diagram with highlighted changed modules
       - Scene 2 (5-8s): Animated code diff walkthrough of selected hunks
    6. Upload .mp4 to PR as a comment via `gh pr comment <url> --body-file <md_with_video>`
    7. Store video URL in SolveRun.diagnostics["video_url"]
    """
    logger.info("Video generation not yet implemented for PR %s", pr_url)
