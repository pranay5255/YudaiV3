from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from yudai.daifuUserAgent.workflow_state import (  # noqa: E402
    EXECUTION_OBJECTIVE_MAX_CHARS,
    apply_workflow_context_patch,
    build_execution_objective,
    select_workflow_issue,
)


def test_apply_workflow_context_patch_omitted_affected_systems_preserves_existing():
    session = SimpleNamespace(
        mode_metadata={
            "workflow_context": {
                "affected_systems": ["api"],
                "note": "preserve",
            }
        }
    )

    apply_workflow_context_patch(session, {}, set())

    assert session.mode_metadata["workflow_context"] == {
        "affected_systems": ["api"],
        "note": "preserve",
    }


def test_apply_workflow_context_patch_empty_affected_systems_clears_existing():
    session = SimpleNamespace(
        mode_metadata={
            "workflow_context": {
                "affected_systems": ["api"],
            }
        }
    )

    apply_workflow_context_patch(
        session,
        {"affected_systems": []},
        {"affected_systems"},
    )

    assert "workflow_context" not in session.mode_metadata


def test_select_workflow_issue_with_url_sets_number_and_url_together():
    session = SimpleNamespace(
        architect_issue_number=None,
        architect_issue_url=None,
        mode_metadata={},
        repo_branch="main",
        repo_name="yudaiv3",
        repo_owner="octocat",
    )

    selected = select_workflow_issue(
        session,
        {
            "github_issue_number": 77,
            "github_issue_url": "https://github.com/octocat/yudaiv3/issues/77",
        },
    )

    assert selected.number == 77
    assert selected.url == "https://github.com/octocat/yudaiv3/issues/77"
    assert session.architect_issue_number == 77
    assert session.architect_issue_url == "https://github.com/octocat/yudaiv3/issues/77"
    assert session.mode_metadata["seed_github_issue_number"] == 77
    assert (
        session.mode_metadata["seed_github_issue_url"]
        == "https://github.com/octocat/yudaiv3/issues/77"
    )


def test_select_workflow_issue_without_url_infers_from_repo_and_never_preserves_stale_url():
    session = SimpleNamespace(
        architect_issue_number=12,
        architect_issue_url="https://github.com/old/repo/issues/12",
        mode_metadata={"seed_github_issue_url": "https://github.com/old/repo/issues/12"},
        repo_branch="main",
        repo_name="yudaiv3",
        repo_owner="octocat",
    )

    select_workflow_issue(session, {"github_issue_number": 88})

    assert session.architect_issue_number == 88
    assert session.architect_issue_url == "https://github.com/octocat/yudaiv3/issues/88"
    assert (
        session.mode_metadata["seed_github_issue_url"]
        == "https://github.com/octocat/yudaiv3/issues/88"
    )


def test_select_workflow_issue_without_url_or_repo_clears_stale_url():
    session = SimpleNamespace(
        architect_issue_number=12,
        architect_issue_url="https://github.com/old/repo/issues/12",
        mode_metadata={"seed_github_issue_url": "https://github.com/old/repo/issues/12"},
        repo_branch=None,
        repo_name=None,
        repo_owner=None,
    )

    select_workflow_issue(session, {"github_issue_number": 88})

    assert session.architect_issue_number == 88
    assert session.architect_issue_url is None
    assert session.mode_metadata["seed_github_issue_url"] is None


def test_build_execution_objective_caps_long_issue_body():
    objective = build_execution_objective(
        {
            "github_issue_number": 191,
            "github_issue_url": "https://github.com/octocat/yudaiv3/issues/191",
            "issue_text_raw": "Body sentence. " + ("x" * 15000),
            "repo_branch": "main",
            "repo_name": "yudaiv3",
            "repo_owner": "octocat",
            "title": "Stabilize workflow objective state",
        }
    )

    assert len(objective) <= EXECUTION_OBJECTIVE_MAX_CHARS
    assert "Resolve GitHub issue #191: Stabilize workflow objective state" in objective
    assert "GitHub issue URL: https://github.com/octocat/yudaiv3/issues/191" in objective
    assert "Repository: octocat/yudaiv3@main" in objective
    assert "Issue details:\nBody sentence." in objective
