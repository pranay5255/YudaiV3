import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from context.chat_context import ChatContext

from utils import utc_now


class DummyQuery:
    def __init__(self, repository):
        self.repository = repository

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.repository


def test_chat_context_summary_uses_cached_json(tmp_path, monkeypatch):
    session = SimpleNamespace(
        session_id="sess-1", repo_context={}, description="Session description"
    )
    repository = SimpleNamespace(
        github_context=None, github_context_updated_at=utc_now()
    )

    db = MagicMock()
    db.query.return_value = DummyQuery(repository)
    db.commit = MagicMock()
    db.rollback = MagicMock()

    monkeypatch.setattr(ChatContext, "CACHE_ROOT", tmp_path)

    chat_context = ChatContext(
        db=db,
        user_id=7,
        repo_owner="octo",
        repo_name="repo",
        session_obj=session,
    )

    cached_payload = {
        "repository": {
            "full_name": "octo/repo",
            "description": "Repository description",
            "language": "Python",
        },
        "recent_issues": [{"number": 1, "title": "Bug"}],
        "recent_commits": [
            {"commit": {"message": "Initial commit", "author": {"name": "Octocat"}}}
        ],
    }

    metadata = chat_context.write_cache(cached_payload)
    repository.github_context = metadata.to_dict()

    summary = asyncio.run(chat_context.build_combined_summary())

    assert "Repository: octo/repo" in summary
    assert "Description: Repository description" in summary
    assert "Recent Open Issues" in summary
    assert session.repo_context["context_string"].startswith("Repository: octo/repo")


def test_chat_context_summary_falls_back_to_gitingest(monkeypatch):
    session = SimpleNamespace(session_id="sess-2", repo_context={})
    repository = SimpleNamespace(github_context=None, github_context_updated_at=None)

    db = MagicMock()
    db.query.return_value = DummyQuery(repository)
    db.commit = MagicMock()
    db.rollback = MagicMock()

    chat_context = ChatContext(
        db=db,
        user_id=5,
        repo_owner="octo",
        repo_name="repo",
        session_obj=session,
    )

    async def fake_gitingest(self):
        return "Repository: octo/repo\nSummary: from gitingest"

    monkeypatch.setattr(ChatContext, "gitingest_fallback", fake_gitingest)
    monkeypatch.setattr(ChatContext, "read_cache", lambda self, meta=None: None)

    summary = asyncio.run(chat_context.build_combined_summary())

    assert "Summary: from gitingest" in summary
    db.commit.assert_called()
