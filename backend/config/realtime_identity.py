"""Canonical identity helpers for org/repo/environment sandbox keys."""

from dataclasses import dataclass
import re
from typing import Tuple

SEGMENT_PATTERN = re.compile(r"[^a-z0-9._-]+")
DASH_PATTERN = re.compile(r"-{2,}")


def normalize_identity_segment(value: str, field_name: str) -> str:
    """
    Normalize a segment used in sandbox identities.

    Rules:
    - trim whitespace
    - lowercase
    - replace unsupported characters with '-'
    - collapse duplicate '-'
    - strip leading/trailing separators
    """
    candidate = (value or "").strip().lower()
    candidate = SEGMENT_PATTERN.sub("-", candidate)
    candidate = DASH_PATTERN.sub("-", candidate)
    candidate = candidate.strip("-._")

    if not candidate:
        raise ValueError(f"{field_name} cannot be empty after normalization")

    return candidate


def normalize_repository(owner: str, repo: str) -> Tuple[str, str]:
    return (
        normalize_identity_segment(owner, "repo_owner"),
        normalize_identity_segment(repo, "repo_name"),
    )


def normalize_environment(environment: str | None, default: str = "main") -> str:
    return normalize_identity_segment(environment or default, "environment")


@dataclass(frozen=True)
class SandboxIdentity:
    org: str
    repo_owner: str
    repo_name: str
    environment: str
    key: str

    @property
    def repository(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


def build_sandbox_identity(
    org: str,
    repo_owner: str,
    repo_name: str,
    environment: str | None,
) -> SandboxIdentity:
    normalized_org = normalize_identity_segment(org, "org")
    normalized_repo_owner, normalized_repo_name = normalize_repository(
        repo_owner, repo_name
    )
    normalized_environment = normalize_environment(environment)
    identity_key = (
        f"{normalized_org}:{normalized_repo_owner}/{normalized_repo_name}:"
        f"{normalized_environment}"
    )

    return SandboxIdentity(
        org=normalized_org,
        repo_owner=normalized_repo_owner,
        repo_name=normalized_repo_name,
        environment=normalized_environment,
        key=identity_key,
    )

