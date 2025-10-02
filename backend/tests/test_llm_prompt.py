import pytest

import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from backend.daifuUserAgent.llm_service import LLMService


def test_build_prompt_with_github_context_includes_repo_details():
    prompt = LLMService._build_daifu_prompt_from_context(
        github_context={
            "repository": {
                "full_name": "octo/repo",
                "description": "Test repository",
                "default_branch": "main",
                "language": "Python",
                "stargazers_count": 42,
                "forks_count": 5,
                "open_issues_count": 3,
                "html_url": "https://github.com/octo/repo",
            },
            "recent_commits": [
                {"sha": "abcdef1", "message": "Initial commit"},
                {"sha": "abcdef2", "message": "Add feature"},
            ],
            "recent_issues": [
                {"number": 1, "title": "Bug report"},
                {"number": 2, "title": "Feature request"},
            ],
            "branches": [{"name": "main"}, {"name": "develop"}],
        },
        conversation=[("User", "Hello")],
        file_contexts=["Context snippet"],
    )

    assert "Repository: octo/repo" in prompt
    assert "Description: Test repository" in prompt
    assert "Recent Commits:" in prompt
    assert "Open Issues:" in prompt
    assert "Repository Branches:" in prompt


def test_build_prompt_with_fallback_summary_when_github_context_missing():
    fallback_summary = "Repository: octo/repo\nDescription: Cached summary"

    prompt = LLMService._build_daifu_prompt_from_context(
        github_context=None,
        conversation=[("User", "Hello")],
        file_contexts=[],
        fallback_repo_summary=fallback_summary,
    )

    assert fallback_summary in prompt
    assert "Recent Commits: Not available (cached summary used)" in prompt
    assert "Open Issues: Not available (cached summary used)" in prompt
    assert "Repository Branches: Not available (cached summary used)" in prompt


def test_generate_response_with_stored_context_passes_fallback(monkeypatch):
    captured = {}

    async def fake_generate_response(*, prompt, model=None, temperature=None, max_tokens=None, timeout=None):
        captured["prompt"] = prompt
        return "ok"

    def fake_build_prompt(*, github_context, conversation, file_contexts, fallback_repo_summary=None):
        captured["builder_args"] = {
            "github_context": github_context,
            "fallback_repo_summary": fallback_repo_summary,
        }
        return "prompt"

    monkeypatch.setattr(LLMService, "generate_response", staticmethod(fake_generate_response))
    monkeypatch.setattr(
        LLMService,
        "_build_daifu_prompt_from_context",
        staticmethod(fake_build_prompt),
    )

    async def _run() -> None:
        result = await LLMService.generate_response_with_stored_context(
            db=None,
            user_id=1,
            github_context=None,
            conversation_history=[("User", "Hello")],
            file_contexts=["Context"],
            fallback_repo_summary="Repository: cached/repo",
        )

        assert captured["builder_args"]["github_context"] is None
        assert captured["builder_args"]["fallback_repo_summary"] == "Repository: cached/repo"
        assert result == "ok"

    asyncio.run(_run())
