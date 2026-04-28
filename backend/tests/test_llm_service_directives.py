import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

stubbed_llm_service = sys.modules.get("yudai.daifuUserAgent.llm_service")
if stubbed_llm_service is not None and not hasattr(stubbed_llm_service, "DaifuParsedResponse"):
    sys.modules.pop("yudai.daifuUserAgent.llm_service", None)

from yudai.daifuUserAgent.llm_service import LLMService  # noqa: E402


def test_format_chat_response_v2_parses_structured_daifu_contract():
    parsed = LLMService.format_chat_response_v2(
        """
        <daifu_response>{
          "text": "I can draft this once we confirm scope.",
          "questions": [{"text": "Which auth flow?", "options": ["JWT", {"id": "oauth", "label": "OAuth login"}]}],
          "probes": [{"query": "find auth middleware"}, "find auth tests"],
          "actions": [{"label": "Start Task", "issue_title": "Fix auth callback", "labels": ["bug"]}],
          "tool_calls": [{"name": "create_github_issue", "args": {"issue_id": "issue_123"}}]
        }</daifu_response>
        Button{"Legacy Button"}
        """
    )

    assert parsed.text == "I can draft this once we confirm scope."
    assert parsed.actions == [
        {
            "action_type": "create_issue",
            "label": "Start Task",
            "issue_title": "Fix auth callback",
            "labels": ["bug"],
        }
    ]
    assert parsed.questions == [
        {
            "text": "Which auth flow?",
            "options": [
                {"id": "jwt", "label": "JWT"},
                {"id": "oauth", "label": "OAuth login"},
            ],
        }
    ]
    assert parsed.probes == [
        {"query": "find auth middleware"},
        {"query": "find auth tests"},
    ]
    assert parsed.tool_calls == [
        {"name": "create_github_issue", "args": {"issue_id": "issue_123"}}
    ]


def test_format_chat_response_v2_parses_questions_probes_and_buttons():
    parsed = LLMService.format_chat_response_v2(
        "\n".join(
            [
                "I need two things before drafting the issue.",
                'Question{"Which auth flow?" options=["JWT", "OAuth login"]}',
                'Probe{"find the auth middleware and database models"}',
                'Button{"Start Task"}',
            ]
        )
    )

    assert parsed.text == "I need two things before drafting the issue."
    assert parsed.actions == [
        {
            "action_type": "create_issue",
            "label": "Start Task",
            "issue_title": None,
            "labels": ["task"],
        }
    ]
    assert parsed.questions == [
        {
            "text": "Which auth flow?",
            "options": [
                {"id": "jwt", "label": "JWT"},
                {"id": "oauth-login", "label": "OAuth login"},
            ],
        }
    ]
    assert parsed.probes == [
        {"query": "find the auth middleware and database models"}
    ]


def test_malformed_structured_daifu_contract_falls_back_to_legacy_directives():
    parsed = LLMService.format_chat_response_v2(
        "\n".join(
            [
                '<daifu_response>{"text": "broken", "questions": [}</daifu_response>',
                "Fallback text",
                'Question{"Which area?" options=[API, UI]}',
                'Probe{"find session routes"}',
            ]
        )
    )

    assert parsed.text == "Fallback text"
    assert parsed.questions == [
        {
            "text": "Which area?",
            "options": [
                {"id": "api", "label": "API"},
                {"id": "ui", "label": "UI"},
            ],
        }
    ]
    assert parsed.probes == [{"query": "find session routes"}]


def test_structured_question_options_are_normalized_and_deduplicated():
    parsed = LLMService.format_chat_response_v2(
        """
        <daifu_response>{
          "text": "Pick one.",
          "questions": [
            {"question": "Which path?", "options": ["API", "API", {"label": "UI polish"}]},
            {"prompt": "Which path?", "options": ["Duplicate question ignored"]}
          ]
        }</daifu_response>
        """
    )

    assert parsed.questions == [
        {
            "text": "Which path?",
            "options": [
                {"id": "api", "label": "API"},
                {"id": "api-2", "label": "API"},
                {"id": "ui-polish", "label": "UI polish"},
            ],
        }
    ]


def test_structured_probe_and_tool_limits_and_filtering():
    parsed = LLMService.format_chat_response_v2(
        """
        <daifu_response>{
          "text": "I will inspect this.",
          "probes": ["one", "two", "three", "four"],
          "tool_calls": [
            {"name": "create_github_issue", "issue_id": "issue_1"},
            {"name": "delete_repository", "args": {"repo": "octo/repo"}},
            {"name": "run_architect_mode", "args": {"objective": "Fix it"}},
            {"tool_name": "run_tester_mode", "objective": "Test it"},
            {"name": "run_coder_mode", "args": {"objective": "Code it"}}
          ]
        }</daifu_response>
        """
    )

    assert parsed.probes == [{"query": "one"}, {"query": "two"}, {"query": "three"}]
    assert parsed.tool_calls == [
        {"name": "create_github_issue", "args": {"issue_id": "issue_1"}},
        {"name": "run_architect_mode", "args": {"objective": "Fix it"}},
        {"name": "run_tester_mode", "args": {"objective": "Test it"}},
    ]


def test_format_chat_response_preserves_legacy_tuple_contract():
    text, actions = LLMService.format_chat_response(
        'Suggested task\nFix auth\nButton{"Start Task"}\nProbe{"find auth files"}'
    )

    assert text == "Suggested task\nFix auth"
    assert actions[0]["label"] == "Start Task"


def test_daifu_prompt_includes_architect_ready_issue_sizing_guidance():
    prompt = LLMService._build_daifu_prompt_from_context(
        conversation=[("User", "Draft issues for improving session handling.")]
    )
    compact_prompt = " ".join(prompt.split())

    assert "Draft Architect-ready GitHub issues" in prompt
    assert "Objective: the user-visible outcome or bug to fix" in prompt
    assert (
        "Repository evidence: the file, route, test, issue, branch, or commit context"
        in prompt
    )
    assert "Scope and out-of-scope: what belongs in this issue" in prompt
    assert "Implementation plan: concrete steps an Architect agent can refine" in prompt
    assert (
        "Likely files: expected files, packages, or tests to inspect or change"
        in prompt
    )
    assert "Acceptance criteria: objective checks for completion" in prompt
    assert "Tests: focused validation that should pass after implementation" in prompt
    assert "Aim for one focused PR per issue" in prompt
    assert "Prefer changes around ~150 LOC or smaller" in prompt
    assert "likely exceeds ~200 LOC" in prompt
    assert "spans unrelated subsystems" in prompt
    assert (
        "ask clarifying questions before drafting or publishing an issue"
        in compact_prompt
    )
