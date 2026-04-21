from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
import asyncio

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from context.chat_context import ChatContext  # noqa: E402


class DummyQuery:
    def __init__(self, repository):
        self.repository = repository

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.repository


def test_chat_context_summary_uses_session_and_repository_metadata():
    session = SimpleNamespace(
        id=None,
        session_id="sess-1",
        repo_context={"summary": "Stored session summary"},
        title="Session title",
        description="Session description",
        repo_branch="main",
        repo_url="https://github.com/octo/repo",
    )
    repository = SimpleNamespace(
        description="Repository description",
        language="Python",
        html_url="https://github.com/octo/repo",
        default_branch="main",
    )

    db = MagicMock()
    db.query.return_value = DummyQuery(repository)
    db.commit = MagicMock()
    db.rollback = MagicMock()

    chat_context = ChatContext(
        db=db,
        user_id=7,
        repo_owner="octo",
        repo_name="repo",
        session_obj=session,
    )

    summary = asyncio.run(chat_context.build_combined_summary())

    assert "Repository: octo/repo" in summary
    assert "Description: Repository description" in summary
    assert "Stored session summary" in summary
    assert session.repo_context["context_string"].startswith("Repository: octo/repo")


def test_chat_context_summary_falls_back_to_repo_identity():
    session = SimpleNamespace(
        id=None,
        session_id="sess-2",
        repo_context={},
        title=None,
        description=None,
        repo_branch="main",
        repo_url="https://github.com/octo/repo",
    )
    repository = None

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

    summary = asyncio.run(chat_context.build_combined_summary())

    assert "Repository: octo/repo" in summary
    assert "Branch: main" in summary
    db.commit.assert_called()
