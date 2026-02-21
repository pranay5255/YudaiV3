import pytest
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config.realtime_identity import (  # noqa: E402
    build_sandbox_identity,
    normalize_environment,
    normalize_identity_segment,
    normalize_repository,
)


def test_normalize_identity_segment_basic():
    assert normalize_identity_segment("  Team Alpha  ", "org") == "team-alpha"
    assert normalize_identity_segment("My.Repo_Name", "repo_name") == "my.repo_name"


def test_normalize_repository():
    owner, repo = normalize_repository("OpenAI-Labs", "Yudai_V3")
    assert owner == "openai-labs"
    assert repo == "yudai_v3"


def test_normalize_environment_default():
    assert normalize_environment(None) == "main"
    assert normalize_environment(" Feature/Realtime ") == "feature-realtime"


def test_build_sandbox_identity_key():
    identity = build_sandbox_identity(
        org="Yudai Org",
        repo_owner="OctoCat",
        repo_name="YudaiV3",
        environment="feature/realtime",
    )

    assert identity.org == "yudai-org"
    assert identity.repository == "octocat/yudaiv3"
    assert identity.environment == "feature-realtime"
    assert identity.key == "yudai-org:octocat/yudaiv3:feature-realtime"


def test_normalize_identity_segment_rejects_empty():
    with pytest.raises(ValueError):
        normalize_identity_segment("___", "repo_name")
