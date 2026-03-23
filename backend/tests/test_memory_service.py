from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from daifuUserAgent.session_service import MemoryService


class DummyQuery:
    def __init__(self, messages):
        self._messages = messages

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return self._messages


def test_store_facts_preserves_existing_memories_and_snapshot():
    session = SimpleNamespace(
        repo_context={
            "facts_and_memories": {
                "memories": ["Need follow-up tests"],
            },
            "session_snapshot": {"trigger": "github_issue_created"},
        }
    )

    stored = MemoryService.store_facts(
        session,
        facts=["FastAPI app lives in backend/app.py"],
        highlights=["backend/app.py"],
    )

    assert stored["facts"] == ["FastAPI app lives in backend/app.py"]
    assert stored["highlights"] == ["backend/app.py"]
    assert stored["memories"] == ["Need follow-up tests"]
    assert session.repo_context["session_snapshot"]["trigger"] == "github_issue_created"


def test_append_memories_keeps_a_rolling_window_of_thirty():
    existing = [f"Memory {index}" for index in range(30)]
    session = SimpleNamespace(
        repo_context={
            "facts_and_memories": {
                "facts": ["FastAPI app lives in backend/app.py"],
                "memories": existing,
            }
        }
    )

    appended = MemoryService.append_memories(
        session,
        new_memories=["Memory 30", "Memory 31", "Memory 31"],
    )

    stored = session.repo_context["facts_and_memories"]["memories"]
    assert appended == ["Memory 30", "Memory 31"]
    assert len(stored) == 30
    assert stored[0] == "Memory 2"
    assert stored[-1] == "Memory 31"


def test_build_bootstrap_context_includes_snapshot_and_github_refs():
    session = SimpleNamespace(
        repo_context={
            "facts_and_memories": {
                "facts": ["FastAPI app lives in backend/app.py"],
                "memories": ["Need websocket retry handling"],
                "highlights": ["backend/app.py"],
            },
            "session_snapshot": {
                "trigger": "pull_request_created",
                "github": {"issue_number": 12, "pr_number": 44},
                "messages": [
                    {
                        "role": "user",
                        "text": "Resume the websocket retry fix before merging.",
                    }
                ],
            },
        }
    )

    context = MemoryService.build_bootstrap_context(session)

    assert context is not None
    assert "FastAPI app lives in backend/app.py" in context
    assert "Need websocket retry handling" in context
    assert "Linked Issue: #12" in context
    assert "Linked PR: #44" in context
    assert "Resume the websocket retry fix before merging." in context


def test_save_session_snapshot_captures_github_refs_and_trigger():
    messages = [
        SimpleNamespace(
            sender_type="user",
            message_text="Please create the implementation issue and open the PR after tests pass.",
        ),
        SimpleNamespace(
            sender_type="assistant",
            message_text="I will create the issue first and capture the review context.",
        ),
    ]
    db = MagicMock()
    db.query.return_value = DummyQuery(messages)

    session = SimpleNamespace(
        id=7,
        session_id="session_123",
        repo_context={},
        repo_owner="octo",
        repo_name="repo",
        repo_branch="main",
        architect_issue_number=12,
        architect_issue_url="https://github.com/octo/repo/issues/12",
        coder_pr_number=44,
        coder_pr_url="https://github.com/octo/repo/pull/44",
        workflow_completed_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )

    snapshot = MemoryService.save_session_snapshot(
        db,
        session,
        trigger="pull_request_created",
    )

    assert snapshot is not None
    assert snapshot["trigger"] == "pull_request_created"
    assert snapshot["github"]["issue_number"] == 12
    assert snapshot["github"]["pr_number"] == 44
    assert snapshot["session"]["session_id"] == "session_123"
    assert session.repo_context["session_snapshot"]["github"]["pr_url"].endswith("/44")
