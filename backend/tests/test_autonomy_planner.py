import os
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/autonomy-planner-tests.db")

from yudai.models import SessionMode  # noqa: E402
from yudai.realtime.autonomy_planner import DaifuAutonomyPlanner  # noqa: E402


def test_planner_fallback_selects_next_remaining_mode():
    planner = DaifuAutonomyPlanner()

    decision = planner.fallback_decision(
        objective="Fix auth",
        remaining_modes=[SessionMode.TESTER.value, SessionMode.CODER.value],
        completed_mode=SessionMode.ARCHITECT.value,
        result={"status": "complete"},
    )

    assert decision.action == "run_tester_mode"
    assert decision.workflow_mode == SessionMode.TESTER.value
    assert decision.source == "fallback"


def test_planner_rejects_unsupported_action_with_fallback():
    planner = DaifuAutonomyPlanner()
    fallback = planner.fallback_decision(
        objective="Fix auth",
        remaining_modes=[SessionMode.CODER.value],
        completed_mode=SessionMode.TESTER.value,
        result={"status": "complete"},
    )

    decision = planner._normalize_decision(
        {"action": "delete_repository", "objective": "bad"},
        fallback=fallback,
    )

    assert decision.action == "run_coder_mode"
    assert decision.source == "fallback"
