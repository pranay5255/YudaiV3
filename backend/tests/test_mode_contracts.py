import json
from pathlib import Path
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from yudai.realtime.mode_contracts import (  # noqa: E402
    CHANGED_FILES_END,
    CHANGED_FILES_START,
    ModeContractError,
    extract_changed_files_from_output,
    parse_mode_contract,
    validate_mode_changed_files,
)


def test_parse_architect_contract_normalizes_questions():
    payload = {
        "mode": "architect",
        "issue_number": 175,
        "issue_url": "https://github.com/pranay5255/YudaiV3/issues/175",
        "context_file": "/workspace/repo/.yudai/context.md",
        "questions": [
            "Which runtime path should be treated as canonical?",
            {
                "prompt": "Should Tester write integration tests?",
                "options": ["Yes", "No"],
            },
        ],
        "ready_for_tester": False,
    }

    parsed = parse_mode_contract("architect", "analysis\n" + json.dumps(payload))

    assert parsed["mode"] == "architect"
    assert parsed["issue_number"] == 175
    assert parsed["ready_for_tester"] is False
    assert [question["prompt"] for question in parsed["questions"]] == [
        "Which runtime path should be treated as canonical?",
        "Should Tester write integration tests?",
    ]
    assert parsed["questions"][1]["options"][0] == {"id": "option_1", "label": "Yes"}


def test_parse_mode_contract_rejects_missing_final_json():
    with pytest.raises(ModeContractError, match="required final JSON contract"):
        parse_mode_contract("tester", "all tests were added")


def test_parse_mode_contract_rejects_wrong_mode_json():
    payload = {
        "mode": "architect",
        "issue_number": 175,
        "issue_url": "https://github.com/pranay5255/YudaiV3/issues/175",
        "context_file": "/workspace/repo/.yudai/context.md",
        "questions": [],
        "ready_for_tester": True,
    }

    with pytest.raises(ModeContractError, match="running mode"):
        parse_mode_contract("tester", json.dumps(payload))


def test_parse_tester_contract_requires_changed_tests():
    payload = {
        "mode": "tester",
        "test_branch": "yudai/issue-175-tests",
        "tests_changed": [],
        "expected_failures": [],
    }

    with pytest.raises(ModeContractError, match="tests_changed"):
        parse_mode_contract("tester", json.dumps(payload))


def test_parse_coder_contract_requires_pr_metadata_and_tests():
    payload = {
        "mode": "coder",
        "pr_url": "https://github.com/pranay5255/YudaiV3/pull/211",
        "pr_number": 211,
        "test_branch": "yudai/issue-175-tests",
        "tests_run": ["pytest backend/tests/test_mode_orchestrator.py"],
    }

    parsed = parse_mode_contract("coder", json.dumps(payload))

    assert parsed["pr_number"] == 211
    assert parsed["tests_run"] == ["pytest backend/tests/test_mode_orchestrator.py"]


def test_extract_changed_files_from_output_marker_payload():
    output = (
        "stdout\n"
        f"{CHANGED_FILES_START}\n"
        '[".yudai/context.md", "backend/tests/test_mode_orchestrator.py"]\n'
        f"{CHANGED_FILES_END}\n"
    )

    assert extract_changed_files_from_output(output) == [
        ".yudai/context.md",
        "backend/tests/test_mode_orchestrator.py",
    ]


def test_role_boundary_validation_blocks_architect_source_changes():
    with pytest.raises(ModeContractError, match="outside its boundary"):
        validate_mode_changed_files(
            "architect",
            [".yudai/context.md", "backend/yudai/realtime/mode_orchestrator.py"],
        )


def test_role_boundary_validation_allows_tester_test_and_fixture_changes():
    assert validate_mode_changed_files(
        "tester",
        [
            ".yudai/context.md",
            "backend/tests/test_mode_orchestrator.py",
            "src/components/__fixtures__/workflow.json",
            "src/components/AgentWorkbench.test.tsx",
        ],
    ) == [
        ".yudai/context.md",
        "backend/tests/test_mode_orchestrator.py",
        "src/components/__fixtures__/workflow.json",
        "src/components/AgentWorkbench.test.tsx",
    ]


def test_role_boundary_validation_blocks_tester_source_changes():
    with pytest.raises(ModeContractError, match="outside its boundary"):
        validate_mode_changed_files("tester", ["backend/yudai/daifuUserAgent/session_routes.py"])
