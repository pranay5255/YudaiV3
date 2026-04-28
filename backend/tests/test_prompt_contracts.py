import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from yudai.daifuUserAgent.IssueOps import IssueService  # noqa: E402


MODE_CONFIG_DIR = BACKEND_ROOT / "yudai" / "realtime" / "mswea_mode_configs"


def _mode_config(name: str) -> str:
    return (MODE_CONFIG_DIR / name / "config.yaml").read_text(encoding="utf-8")


def test_issue_generation_prompt_is_architect_ready_not_runbook_first():
    prompt = IssueService(db=None)._build_issue_generation_prompt(
        title="Fix reconnect handling",
        description="Chat reconnect drops session state.",
        priority="high",
        chat_messages=[{"isUser": True, "content": "Please fix reconnects."}],
        repo_context="src/hooks/useSessionWebSocket.ts handles reconnect state.",
    )

    assert "Architect-ready GitHub issues" in prompt
    assert "Architect -> Tester -> Coder pipeline" in prompt
    assert "Repository evidence" in prompt
    assert "Scope (what this issue includes)" in prompt
    assert "Out of scope" in prompt
    assert "Likely files" in prompt
    assert "Tests (focused validation Tester should add or update)" in prompt
    assert "Aim for one focused PR per issue" in prompt
    assert "likely exceeds 200 LOC" in prompt
    assert "SubagentExecutor" in prompt
    assert "deterministic Runbook" not in prompt
    assert "Steps to reproduce" not in prompt


def test_mswea_mode_configs_define_current_stage_result_contracts():
    architect = _mode_config("architect")
    tester = _mode_config("tester")
    coder = _mode_config("coder")

    assert "Do not create a GitHub issue." in architect
    assert "Do not create a pull request." in architect
    assert "`mode`, `issue_number`, `issue_url`, `context_file`, `questions`, `ready_for_tester`, `stage_result`" in architect
    assert "`status`: `complete` when ready for Tester, otherwise `blocked`" in architect
    assert "`ready_for_tester`: boolean matching the top-level value" in architect

    assert "Do not implement the feature or bug fix." in tester
    assert "tests must be exclusive to the GitHub issue at hand" in tester
    assert "`mode`, `issue_number`, `context_file`, `test_branch`, `tests_changed`, `expected_failures`, `stage_result`" in tester
    assert "`setup_commands`: any setup commands Coder should run" in tester
    assert "Do not emit PR metadata; only Coder mode opens pull requests" in tester

    assert "Use or compare against the provided tester branch." in coder
    assert "Open the pull request only after focused tests" in coder
    assert "`mode`, `issue_number`, `context_file`, `test_branch`, `pr_url`, `pr_number`, `tests_run`, `stage_result`" in coder
    assert "`pr_url` and `pr_number`" in coder
    assert "Final output must include parseable `pr_url` and `pr_number`" in coder


def test_probe_config_stays_read_only_daifu_support_context():
    probe = _mode_config("probe")

    assert "support context for Daifu's next response" in probe
    assert "Do NOT create issues, PRs, or modify any source files." in probe
    assert "You may write only to `$YUDAI_PROBE_OUTPUT`" in probe
    assert "Do not create or update GitHub issues or pull requests" in probe
