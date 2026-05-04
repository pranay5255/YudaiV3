"""Small workflow-state boundary helpers for session issue execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Set


EXECUTION_OBJECTIVE_MAX_CHARS = 10000
TRUNCATION_SUFFIX = "..."
_ISSUE_URL_RE = re.compile(
    r"https?://github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)(?:[/?#].*)?$"
)


@dataclass(frozen=True)
class WorkflowIssueRef:
    number: Optional[int]
    url: Optional[str]
    title: str
    repo_owner: Optional[str]
    repo_name: Optional[str]
    repo_branch: Optional[str]
    body: str

    @property
    def repository_label(self) -> Optional[str]:
        if self.repo_owner and self.repo_name:
            label = f"{self.repo_owner}/{self.repo_name}"
            return f"{label}@{self.repo_branch}" if self.repo_branch else label
        return None


def apply_workflow_context_patch(
    session: Any,
    patch: Any,
    fields_set: Optional[Iterable[str]],
) -> None:
    """Apply explicit workflow context updates without erasing omitted fields."""

    fields = _normalize_fields_set(patch, fields_set)
    if "affected_systems" not in fields:
        return

    metadata = dict(getattr(session, "mode_metadata", None) or {})
    affected_systems = _coerce_string_list(_value_from_ref(patch, "affected_systems"))
    if not affected_systems:
        metadata.pop("workflow_context", None)
    else:
        workflow_context = metadata.get("workflow_context")
        if not isinstance(workflow_context, dict):
            workflow_context = {}
        metadata["workflow_context"] = {
            **workflow_context,
            "affected_systems": affected_systems,
        }

    session.mode_metadata = metadata


def select_workflow_issue(session: Any, issue_ref: Any) -> WorkflowIssueRef:
    """Select one GitHub issue and replace session issue metadata as one unit."""

    normalized = _normalize_issue_ref(issue_ref, session=session)
    session.architect_issue_number = normalized.number
    session.architect_issue_url = normalized.url

    metadata = dict(getattr(session, "mode_metadata", None) or {})
    metadata["seed_github_issue_number"] = normalized.number
    metadata["seed_github_issue_url"] = normalized.url
    session.mode_metadata = metadata

    return normalized


def build_execution_objective(
    issue_ref: Any,
    max_chars: int = EXECUTION_OBJECTIVE_MAX_CHARS,
) -> str:
    """Build a compact issue execution objective under the backend request limit."""

    normalized = _normalize_issue_ref(issue_ref)
    issue_label = (
        f"#{normalized.number}"
        if normalized.number is not None
        else normalized.url or "selected issue"
    )
    summary = f"Resolve GitHub issue {issue_label}"
    if normalized.title:
        summary = f"{summary}: {normalized.title}"

    sections = [summary]
    if normalized.url:
        sections.append(f"GitHub issue URL: {normalized.url}")
    if normalized.repository_label:
        sections.append(f"Repository: {normalized.repository_label}")

    body = _compact_text(normalized.body)
    if body:
        fixed_without_body = "\n\n".join([*sections, "Issue details:\n"])
        body_budget = max_chars - len(fixed_without_body)
        if body_budget > 0:
            sections.append(f"Issue details:\n{_cap_text(body, body_budget)}")
        else:
            return _cap_text("\n\n".join(sections), max_chars)

    return _cap_text("\n\n".join(part for part in sections if part.strip()), max_chars)


def _normalize_fields_set(patch: Any, fields_set: Optional[Iterable[str]]) -> Set[str]:
    if fields_set is not None:
        return {str(field) for field in fields_set}

    model_fields_set = getattr(patch, "model_fields_set", None)
    if model_fields_set is not None:
        return {str(field) for field in model_fields_set}

    legacy_fields_set = getattr(patch, "__fields_set__", None)
    if legacy_fields_set is not None:
        return {str(field) for field in legacy_fields_set}

    if isinstance(patch, Mapping):
        return {str(field) for field in patch.keys()}

    return set()


def _normalize_issue_ref(issue_ref: Any, *, session: Any = None) -> WorkflowIssueRef:
    url = _first_string(
        issue_ref,
        "github_issue_url",
        "issue_url",
        "html_url",
        "url",
    )
    parsed_owner, parsed_name, parsed_number = _parse_issue_url(url)
    number = _first_int(
        issue_ref,
        "github_issue_number",
        "issue_number",
        "number",
    )
    if number is None:
        number = parsed_number

    repo_owner = _first_string(issue_ref, "repo_owner", "owner") or parsed_owner
    repo_name = _first_string(issue_ref, "repo_name", "name") or parsed_name
    if session is not None:
        repo_owner = repo_owner or _clean_string(getattr(session, "repo_owner", None))
        repo_name = repo_name or _clean_string(getattr(session, "repo_name", None))

    repo_full_name = _first_string(
        issue_ref,
        "repo_full_name",
        "repository_full_name",
        "full_name",
    )
    if repo_full_name and "/" in repo_full_name and (not repo_owner or not repo_name):
        owner_part, name_part = repo_full_name.split("/", 1)
        repo_owner = repo_owner or _clean_string(owner_part)
        repo_name = repo_name or _clean_string(name_part)

    repo_branch = _first_string(issue_ref, "repo_branch", "branch")
    if session is not None:
        repo_branch = repo_branch or _clean_string(getattr(session, "repo_branch", None))

    if not url and number is not None and repo_owner and repo_name:
        url = f"https://github.com/{repo_owner}/{repo_name}/issues/{number}"

    return WorkflowIssueRef(
        number=number,
        url=url,
        title=_first_string(issue_ref, "title") or "",
        repo_owner=repo_owner,
        repo_name=repo_name,
        repo_branch=repo_branch,
        body=_first_string(issue_ref, "issue_text_raw", "body", "description") or "",
    )


def _value_from_ref(ref: Any, key: str) -> Any:
    if isinstance(ref, Mapping):
        return ref.get(key)
    return getattr(ref, key, None)


def _first_string(ref: Any, *keys: str) -> Optional[str]:
    for key in keys:
        value = _value_from_ref(ref, key)
        if isinstance(value, Mapping):
            value = value.get("login") or value.get("full_name") or value.get("name")
        cleaned = _clean_string(value)
        if cleaned:
            return cleaned
    return None


def _first_int(ref: Any, *keys: str) -> Optional[int]:
    for key in keys:
        value = _value_from_ref(ref, key)
        parsed = _to_int(value)
        if parsed is not None:
            return parsed
    return None


def _parse_issue_url(url: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[int]]:
    if not url:
        return None, None, None

    match = _ISSUE_URL_RE.match(url)
    if not match:
        return None, None, None

    owner, name, number = match.groups()
    return owner, name, _to_int(number)


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _compact_text(value: str) -> str:
    return " ".join((value or "").split())


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_compact_text(value)] if value.strip() else []
    if isinstance(value, Iterable):
        return [
            cleaned
            for item in value
            if (cleaned := _clean_string(item)) is not None
        ]
    return []


def _to_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cap_text(value: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= len(TRUNCATION_SUFFIX):
        return value[:max_chars]
    return value[: max_chars - len(TRUNCATION_SUFFIX)].rstrip() + TRUNCATION_SUFFIX
