import sys
import types
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


fake_sentence_transformers = types.ModuleType("sentence_transformers")
fake_sentence_transformers.SentenceTransformer = type("SentenceTransformer", (), {})
sys.modules.setdefault("sentence_transformers", fake_sentence_transformers)

stubbed_llm_service = sys.modules.get("daifuUserAgent.llm_service")
if stubbed_llm_service is not None and not hasattr(stubbed_llm_service, "DaifuParsedResponse"):
    sys.modules.pop("daifuUserAgent.llm_service", None)

from daifuUserAgent.llm_service import LLMService  # noqa: E402


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


def test_format_chat_response_preserves_legacy_tuple_contract():
    text, actions = LLMService.format_chat_response(
        'Suggested task\nFix auth\nButton{"Start Task"}\nProbe{"find auth files"}'
    )

    assert text == "Suggested task\nFix auth"
    assert actions[0]["label"] == "Start Task"
