"""Strict MSWEA mode-result contracts for the fixed 3-mode pipeline."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional


CONTRACT_VERSION = "mswea-mode-contract-v1"
CHANGED_FILES_START = "__YUDAI_CHANGED_FILES_START__"
CHANGED_FILES_END = "__YUDAI_CHANGED_FILES_END__"

_VALID_MODES = {"architect", "tester", "coder"}
_PR_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
_ISSUE_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/issues/\d+")


class ModeContractError(ValueError):
    """Raised when an MSWEA mode output violates the controller contract."""


def normalize_mode(value: Any) -> str:
    mode = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if mode in {"architect_mode", "architecture"}:
        return "architect"
    if mode in {"tester_mode", "test_writer", "test_writer_mode"}:
        return "tester"
    if mode in {"coder_mode", "code"}:
        return "coder"
    return mode


def parse_mode_contract(mode: str, output_text: str) -> Dict[str, Any]:
    """Parse and validate the final JSON contract for a mode run."""

    expected_mode = normalize_mode(mode)
    if expected_mode not in _VALID_MODES:
        raise ModeContractError(f"Unsupported MSWEA mode contract: {mode}")

    wrong_mode_seen: Optional[str] = None
    for line in reversed((output_text or "").splitlines()):
        raw = line.strip()
        if not raw.startswith("{") or not raw.endswith("}"):
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        payload_mode = normalize_mode(payload.get("mode"))
        if payload_mode != expected_mode:
            if payload_mode:
                wrong_mode_seen = payload_mode
            continue
        return validate_mode_contract(expected_mode, payload)

    if wrong_mode_seen:
        raise ModeContractError(
            f"MSWEA {expected_mode} mode did not emit a final JSON contract "
            f"for the running mode; saw mode={wrong_mode_seen!r}"
        )
    raise ModeContractError(
        f"MSWEA {expected_mode} mode did not emit the required final JSON contract"
    )


def validate_mode_contract(mode: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    if normalize_mode(payload.get("mode")) != normalized_mode:
        raise ModeContractError(f"MSWEA contract mode mismatch for {normalized_mode}")

    if normalized_mode == "architect":
        issue_number = _require_int(payload, "issue_number", mode=normalized_mode)
        issue_url = _require_non_empty_str(payload, "issue_url", mode=normalized_mode)
        if not _ISSUE_URL_PATTERN.fullmatch(issue_url):
            raise ModeContractError("MSWEA architect contract field issue_url is not a GitHub issue URL")
        context_file = _require_non_empty_str(payload, "context_file", mode=normalized_mode)
        ready_for_tester = payload.get("ready_for_tester")
        if not isinstance(ready_for_tester, bool):
            raise ModeContractError("MSWEA architect contract field ready_for_tester must be boolean")
        questions = _normalize_questions(payload.get("questions"), mode=normalized_mode)
        if not ready_for_tester and not questions:
            raise ModeContractError(
                "MSWEA architect contract marked ready_for_tester=false without questions"
            )
        return {
            "contract_version": CONTRACT_VERSION,
            "mode": normalized_mode,
            "issue_number": issue_number,
            "issue_url": issue_url,
            "context_file": context_file,
            "questions": questions,
            "ready_for_tester": ready_for_tester,
        }

    if normalized_mode == "tester":
        test_branch = _require_non_empty_str(payload, "test_branch", mode=normalized_mode)
        tests_changed = _require_str_list(payload, "tests_changed", mode=normalized_mode)
        expected_failures = _normalize_list(payload.get("expected_failures"), key="expected_failures", mode=normalized_mode)
        return {
            "contract_version": CONTRACT_VERSION,
            "mode": normalized_mode,
            "test_branch": test_branch,
            "tests_changed": tests_changed,
            "expected_failures": expected_failures,
        }

    if normalized_mode == "coder":
        pr_url = _require_non_empty_str(payload, "pr_url", mode=normalized_mode)
        if not _PR_URL_PATTERN.fullmatch(pr_url):
            raise ModeContractError("MSWEA coder contract field pr_url is not a GitHub pull request URL")
        pr_number = _require_int(payload, "pr_number", mode=normalized_mode)
        test_branch = _require_non_empty_str(payload, "test_branch", mode=normalized_mode)
        tests_run = _require_str_list(payload, "tests_run", mode=normalized_mode)
        return {
            "contract_version": CONTRACT_VERSION,
            "mode": normalized_mode,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "test_branch": test_branch,
            "tests_run": tests_run,
        }

    raise ModeContractError(f"Unsupported MSWEA mode contract: {mode}")


def extract_changed_files_from_output(output_text: str) -> List[str]:
    start = (output_text or "").rfind(CHANGED_FILES_START)
    if start < 0:
        return []
    start += len(CHANGED_FILES_START)
    end = output_text.find(CHANGED_FILES_END, start)
    if end < 0:
        return []
    raw = output_text[start:end].strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return normalize_changed_files(payload)


def normalize_changed_files(files: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for item in files:
        path = str(item or "").strip().replace("\\", "/")
        if not path:
            continue
        while path.startswith("./"):
            path = path[2:]
        path = path.lstrip("/")
        if path and path not in seen:
            seen.add(path)
            normalized.append(path)
    return normalized


def validate_mode_changed_files(mode: str, changed_files: Iterable[Any]) -> List[str]:
    normalized_mode = normalize_mode(mode)
    files = normalize_changed_files(changed_files)
    disallowed: List[str] = []

    for path in files:
        if _is_yudai_artifact_path(path):
            continue
        if normalized_mode == "architect":
            disallowed.append(path)
        elif normalized_mode == "tester" and not _is_test_or_fixture_path(path):
            disallowed.append(path)

    if disallowed:
        raise ModeContractError(
            f"MSWEA {normalized_mode} mode changed files outside its boundary: "
            + ", ".join(disallowed[:8])
        )
    return files


def _require_non_empty_str(payload: Dict[str, Any], key: str, *, mode: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModeContractError(f"MSWEA {mode} contract missing non-empty field {key}")
    return value.strip()


def _require_int(payload: Dict[str, Any], key: str, *, mode: str) -> int:
    value = payload.get(key)
    try:
        if value is None or str(value).strip() == "":
            raise ValueError
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ModeContractError(f"MSWEA {mode} contract missing integer field {key}") from None


def _require_str_list(payload: Dict[str, Any], key: str, *, mode: str) -> List[str]:
    values = _normalize_list(payload.get(key), key=key, mode=mode)
    if not values:
        raise ModeContractError(f"MSWEA {mode} contract field {key} must not be empty")
    if not all(isinstance(item, str) for item in values):
        raise ModeContractError(f"MSWEA {mode} contract field {key} must contain strings")
    return [str(item).strip() for item in values if str(item).strip()]


def _normalize_list(value: Any, *, key: str, mode: str) -> List[Any]:
    if value is None:
        raise ModeContractError(f"MSWEA {mode} contract missing list field {key}")
    if not isinstance(value, list):
        raise ModeContractError(f"MSWEA {mode} contract field {key} must be a list")
    normalized: List[Any] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
        elif isinstance(item, dict):
            normalized.append(item)
        elif item is not None:
            normalized.append(str(item).strip())
    return normalized


def _normalize_questions(value: Any, *, mode: str) -> List[Dict[str, Any]]:
    raw_questions = _normalize_list(value, key="questions", mode=mode)
    questions: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_questions, start=1):
        if isinstance(item, str):
            prompt = item.strip()
            options: List[Dict[str, str]] = []
            multi_select = False
        elif isinstance(item, dict):
            prompt = str(
                item.get("prompt")
                or item.get("question")
                or item.get("question_text")
                or ""
            ).strip()
            options = _normalize_options(item.get("options"))
            multi_select = bool(item.get("multi_select"))
        else:
            prompt = str(item or "").strip()
            options = []
            multi_select = False

        if not prompt:
            raise ModeContractError("MSWEA architect contract contains an empty question")
        questions.append(
            {
                "id": f"architect_question_{index}",
                "prompt": prompt,
                "options": options,
                "multi_select": multi_select,
            }
        )
    return questions


def _normalize_options(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    options: List[Dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        if isinstance(item, str):
            option_id = f"option_{index}"
            label = item.strip()
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("text") or item.get("value") or "").strip()
            option_id = str(item.get("id") or label or f"option_{index}").strip()
        else:
            continue
        if not label:
            continue
        if option_id in seen:
            option_id = f"{option_id}_{index}"
        seen.add(option_id)
        options.append({"id": option_id, "label": label})
    return options


def _is_yudai_artifact_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    return normalized == ".yudai/context.md" or normalized.startswith(".yudai/")


def _is_test_or_fixture_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    lower = normalized.lower()
    parts = [part.lower() for part in PurePosixPath(lower).parts]
    if any(part in {"test", "tests", "__tests__", "fixture", "fixtures", "__fixtures__"} for part in parts):
        return True
    name = PurePosixPath(lower).name
    return (
        name == "conftest.py"
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )
