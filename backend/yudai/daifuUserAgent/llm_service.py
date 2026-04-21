"""
Centralized LLM Service for DAifu Agent
Eliminates duplication and standardizes LLM calls across chat endpoints
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status
from yudai.config import get_model_config
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class DaifuParsedResponse:
    text: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    questions: List[Dict[str, Any]] = field(default_factory=list)
    probes: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


class LLMService:
    """Centralized service for LLM interactions"""

    # Standard model configuration
    DEFAULT_MODEL = "x-ai/grok-4-fast"
    DEFAULT_TEMPERATURE = 0.6
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TIMEOUT = 30

    BUTTON_ACTION_PATTERN = re.compile(
        r'Button\{\s*"(?P<label>[^"]+)"\s*\}', re.IGNORECASE
    )
    QUESTION_DIRECTIVE_PATTERN = re.compile(
        r'Question\{\s*"(?P<text>[^"]+)"(?:\s+options=\[(?P<options>[^\]]*)\])?\s*\}',
        re.IGNORECASE,
    )
    PROBE_DIRECTIVE_PATTERN = re.compile(
        r'Probe\{\s*"(?P<query>[^"]+)"\s*\}',
        re.IGNORECASE,
    )
    TOOL_DIRECTIVE_PATTERN = re.compile(
        r'Tool\{\s*"(?P<name>[^"]+)"(?P<body>.*?)\}',
        re.IGNORECASE | re.DOTALL,
    )
    DAIFU_RESPONSE_BLOCK_PATTERN = re.compile(
        r"<daifu_response>\s*(?P<payload>\{.*?\})\s*</daifu_response>",
        re.IGNORECASE | re.DOTALL,
    )
    FENCED_JSON_PATTERN = re.compile(
        r"```(?:json)?\s*(?P<payload>\{.*?\})\s*```",
        re.IGNORECASE | re.DOTALL,
    )
    ALLOWED_TOOL_NAMES = {
        "create_github_issue",
        "run_architect_mode",
        "run_tester_mode",
        "run_coder_mode",
    }

    @staticmethod
    def _extract_suggested_task_titles(message_text: str) -> List[str]:
        lines = [line.strip() for line in message_text.splitlines()]
        titles: List[str] = []
        for index, line in enumerate(lines):
            if line.lower().startswith("suggested task"):
                for next_line in lines[index + 1 :]:
                    if next_line:
                        titles.append(next_line)
                        break
        return titles

    @staticmethod
    def _derive_labels(label: str, title: Optional[str]) -> List[str]:
        combined = f"{label} {title or ''}".lower()
        labels: List[str] = []
        if "bug" in combined:
            labels.append("bug")
        if "enhancement" in combined:
            labels.append("enhancement")
        if "task" in combined and "bug" not in combined and "enhancement" not in combined:
            labels.append("task")
        return labels

    @staticmethod
    def format_chat_response(message_text: str) -> Tuple[str, List[Dict[str, Any]]]:
        parsed = LLMService.format_chat_response_v2(message_text)
        return parsed.text, parsed.actions

    @staticmethod
    def format_chat_response_v2(message_text: str) -> DaifuParsedResponse:
        if not message_text:
            return DaifuParsedResponse()

        structured = LLMService._parse_structured_response(message_text)
        if structured is not None:
            return structured

        actions: List[Dict[str, Any]] = []
        questions: List[Dict[str, Any]] = []
        probes: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []

        matches = list(LLMService.BUTTON_ACTION_PATTERN.finditer(message_text))
        suggested_titles = LLMService._extract_suggested_task_titles(message_text)

        for index, match in enumerate(matches):
            label = match.group("label").strip()
            issue_title = suggested_titles[index] if index < len(suggested_titles) else None
            LLMService._append_unique_action(
                actions,
                {
                    "action_type": "create_issue",
                    "label": label,
                    "issue_title": issue_title,
                    "labels": LLMService._derive_labels(label, issue_title),
                }
            )

        for match in LLMService.QUESTION_DIRECTIVE_PATTERN.finditer(message_text):
            text = match.group("text").strip()
            if not text:
                continue
            LLMService._append_unique_question(
                questions,
                {
                    "text": text,
                    "options": LLMService._parse_question_options(
                        match.group("options")
                    ),
                }
            )

        for match in LLMService.PROBE_DIRECTIVE_PATTERN.finditer(message_text):
            query = match.group("query").strip()
            if query:
                LLMService._append_unique_probe(probes, {"query": query})

        for match in LLMService.TOOL_DIRECTIVE_PATTERN.finditer(message_text):
            tool_call = LLMService._parse_legacy_tool_directive(match)
            if tool_call:
                LLMService._append_unique_tool_call(tool_calls, tool_call)

        cleaned_text = LLMService.BUTTON_ACTION_PATTERN.sub("", message_text)
        cleaned_text = LLMService.QUESTION_DIRECTIVE_PATTERN.sub("", cleaned_text)
        cleaned_text = LLMService.PROBE_DIRECTIVE_PATTERN.sub("", cleaned_text)
        cleaned_text = LLMService.TOOL_DIRECTIVE_PATTERN.sub("", cleaned_text)
        cleaned_text = LLMService.DAIFU_RESPONSE_BLOCK_PATTERN.sub("", cleaned_text)
        cleaned_text = LLMService.FENCED_JSON_PATTERN.sub("", cleaned_text).strip()
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
        return DaifuParsedResponse(
            text=cleaned_text,
            actions=actions,
            questions=questions,
            probes=probes,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_structured_response(message_text: str) -> Optional[DaifuParsedResponse]:
        payload = LLMService._extract_structured_payload(message_text)
        if payload is None:
            return None

        if isinstance(payload.get("daifu_response"), dict):
            payload = payload["daifu_response"]
        elif isinstance(payload.get("response"), dict):
            payload = payload["response"]

        text = str(payload.get("text") or payload.get("reply") or "").strip()
        actions = LLMService._normalize_actions(payload.get("actions"))
        questions = LLMService._normalize_questions(payload.get("questions"))
        probes = LLMService._normalize_probes(payload.get("probes"))
        tool_calls = LLMService._normalize_tool_calls(
            payload.get("tool_calls") or payload.get("tools")
        )
        return DaifuParsedResponse(
            text=text,
            actions=actions,
            questions=questions,
            probes=probes,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _extract_structured_payload(message_text: str) -> Optional[Dict[str, Any]]:
        candidates: List[str] = []
        for pattern in (
            LLMService.DAIFU_RESPONSE_BLOCK_PATTERN,
            LLMService.FENCED_JSON_PATTERN,
        ):
            match = pattern.search(message_text or "")
            if match:
                candidates.append(match.group("payload"))

        stripped = (message_text or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _normalize_actions(raw_actions: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_actions, list):
            return []
        actions: List[Dict[str, Any]] = []
        for raw in raw_actions:
            if isinstance(raw, str):
                raw = {"label": raw}
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or raw.get("button") or "Start Task").strip()
            if not label:
                continue
            issue_title = raw.get("issue_title") or raw.get("title")
            issue_title = str(issue_title).strip() if issue_title else None
            labels_raw = raw.get("labels")
            labels = [
                str(label_value).strip()
                for label_value in labels_raw
                if str(label_value).strip()
            ] if isinstance(labels_raw, list) else LLMService._derive_labels(label, issue_title)
            action = {
                "action_type": str(raw.get("action_type") or "create_issue").strip(),
                "label": label,
                "issue_title": issue_title,
                "labels": labels,
            }
            if raw.get("issue_description"):
                action["issue_description"] = str(raw["issue_description"]).strip()
            LLMService._append_unique_action(actions, action)
        return actions[:3]

    @staticmethod
    def _normalize_questions(raw_questions: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_questions, list):
            return []
        questions: List[Dict[str, Any]] = []
        for raw in raw_questions:
            if isinstance(raw, str):
                raw = {"text": raw}
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or raw.get("question") or raw.get("prompt") or "").strip()
            if not text:
                continue
            options = LLMService._normalize_question_option_values(raw.get("options"))
            LLMService._append_unique_question(
                questions,
                {
                    "text": text,
                    "options": options,
                },
            )
        return questions[:2]

    @staticmethod
    def _normalize_probes(raw_probes: Any) -> List[Dict[str, str]]:
        if not isinstance(raw_probes, list):
            return []
        probes: List[Dict[str, str]] = []
        for raw in raw_probes:
            query = ""
            if isinstance(raw, str):
                query = raw
            elif isinstance(raw, dict):
                query = str(raw.get("query") or raw.get("question") or "").strip()
            if query:
                LLMService._append_unique_probe(probes, {"query": query})
        return probes[:3]

    @staticmethod
    def _normalize_tool_calls(raw_tool_calls: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_tool_calls, list):
            return []
        tool_calls: List[Dict[str, Any]] = []
        for raw in raw_tool_calls:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("tool_name") or "").strip()
            if name not in LLMService.ALLOWED_TOOL_NAMES:
                continue
            args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
            if not args:
                args = {
                    key: value
                    for key, value in raw.items()
                    if key not in {"name", "tool_name", "args"}
                }
            LLMService._append_unique_tool_call(
                tool_calls,
                {
                    "name": name,
                    "args": args,
                },
            )
        return tool_calls[:3]

    @staticmethod
    def _normalize_question_option_values(raw_options: Any) -> List[Dict[str, str]]:
        if not isinstance(raw_options, list):
            return []
        options: List[Dict[str, str]] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_options):
            if isinstance(raw, dict):
                label = str(raw.get("label") or raw.get("text") or "").strip()
                option_id = str(raw.get("id") or "").strip()
            else:
                label = str(raw or "").strip()
                option_id = ""
            if not label:
                continue
            option_id = option_id or LLMService._slugify_option_id(label) or f"option-{index + 1}"
            base_id = option_id
            suffix = 2
            while option_id in seen:
                option_id = f"{base_id}-{suffix}"
                suffix += 1
            seen.add(option_id)
            options.append({"id": option_id, "label": label})
        return options

    @staticmethod
    def _parse_legacy_tool_directive(match: re.Match[str]) -> Optional[Dict[str, Any]]:
        name = match.group("name").strip()
        if name not in LLMService.ALLOWED_TOOL_NAMES:
            return None
        body = match.group("body") or ""
        args: Dict[str, Any] = {}
        args_match = re.search(r"args\s*=\s*(\{.*\})", body, re.DOTALL)
        if args_match:
            try:
                parsed_args = json.loads(args_match.group(1))
                if isinstance(parsed_args, dict):
                    args.update(parsed_args)
            except json.JSONDecodeError:
                pass
        for key, value in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', body):
            if key != "args":
                args[key] = value
        return {"name": name, "args": args}

    @staticmethod
    def _append_unique_action(actions: List[Dict[str, Any]], action: Dict[str, Any]) -> None:
        key = (
            str(action.get("action_type") or ""),
            str(action.get("label") or ""),
            str(action.get("issue_title") or ""),
        )
        existing = {
            (
                str(item.get("action_type") or ""),
                str(item.get("label") or ""),
                str(item.get("issue_title") or ""),
            )
            for item in actions
        }
        if key not in existing:
            actions.append(action)

    @staticmethod
    def _append_unique_question(questions: List[Dict[str, Any]], question: Dict[str, Any]) -> None:
        text = str(question.get("text") or "").strip().lower()
        if text and text not in {
            str(item.get("text") or "").strip().lower() for item in questions
        }:
            questions.append(question)

    @staticmethod
    def _append_unique_probe(probes: List[Dict[str, str]], probe: Dict[str, str]) -> None:
        query = str(probe.get("query") or "").strip().lower()
        if query and query not in {
            str(item.get("query") or "").strip().lower() for item in probes
        }:
            probes.append(probe)

    @staticmethod
    def _append_unique_tool_call(tool_calls: List[Dict[str, Any]], tool_call: Dict[str, Any]) -> None:
        key = (
            str(tool_call.get("name") or ""),
            json.dumps(tool_call.get("args") or {}, sort_keys=True, default=str),
        )
        existing = {
            (
                str(item.get("name") or ""),
                json.dumps(item.get("args") or {}, sort_keys=True, default=str),
            )
            for item in tool_calls
        }
        if key not in existing:
            tool_calls.append(tool_call)

    @staticmethod
    def _parse_question_options(options_raw: Optional[str]) -> List[Dict[str, str]]:
        if not options_raw:
            return []

        labels: List[str] = []
        try:
            parsed = json.loads(f"[{options_raw}]")
            if isinstance(parsed, list):
                labels = [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            labels = [
                item.strip().strip("'\"")
                for item in options_raw.split(",")
                if item.strip().strip("'\"")
            ]

        options: List[Dict[str, str]] = []
        seen: set[str] = set()
        for index, label in enumerate(labels):
            option_id = LLMService._slugify_option_id(label) or f"option-{index + 1}"
            base_id = option_id
            suffix = 2
            while option_id in seen:
                option_id = f"{base_id}-{suffix}"
                suffix += 1
            seen.add(option_id)
            options.append({"id": option_id, "label": label})
        return options

    @staticmethod
    def _slugify_option_id(label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        return slug[:64]

    @staticmethod
    def get_api_key() -> str:
        """Get OpenRouter API key from environment"""
        api_key = get_model_config().api_key
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENROUTER_API_KEY not configured",
            )
        return api_key

    @staticmethod
    def get_api_url() -> str:
        """Resolve the base URL for chat completions (configurable)."""
        return get_model_config().api_url

    @staticmethod
    async def generate_response(
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> str:
        """
        Generate response from LLM with standardized configuration

        Args:
            prompt: The prompt to send to the LLM
            model: Model to use (defaults to DEFAULT_MODEL)
            temperature: Temperature for generation (defaults to DEFAULT_TEMPERATURE)
            max_tokens: Maximum tokens to generate (defaults to DEFAULT_MAX_TOKENS)
            timeout: Request timeout in seconds (defaults to DEFAULT_TIMEOUT)

        Returns:
            Generated response text

        Raises:
            HTTPException: For API errors or configuration issues
        """
        # Use typed config defaults if not provided.
        model_config = get_model_config()
        model = model or model_config.model_name
        temperature = temperature or model_config.temperature
        max_tokens = max_tokens or model_config.max_tokens
        timeout = timeout or model_config.timeout_seconds

        # request_start is set just before the HTTP call so that logged durations
        # reflect actual network time, not event-loop scheduling delays that can
        # accumulate before this function gets its turn (e.g. blocking embed_text).
        request_start: float = 0.0

        try:
            api_key = LLMService.get_api_key()
            url = LLMService.get_api_url()

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Use explicit per-operation timeouts so that a long LLM generation
            # (read) doesn't get confused with a slow connection (connect).
            httpx_timeout = httpx.Timeout(
                connect=10.0,
                read=float(timeout),
                write=30.0,
                pool=5.0,
            )
            request_start = time.time()
            async with httpx.AsyncClient(timeout=httpx_timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()

                response_data = resp.json()
                reply = response_data["choices"][0]["message"]["content"].strip()

            processing_time = (time.time() - request_start) * 1000
            logger.info(f"LLM response generated in {processing_time:.2f}ms")
            return reply

        except httpx.TimeoutException as e:
            processing_time = (time.time() - request_start) * 1000
            logger.error(f"LLM request timeout after {processing_time:.2f}ms: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="LLM request timed out",
            )
        except httpx.HTTPStatusError as e:
            processing_time = (time.time() - request_start) * 1000
            content = e.response.text if e.response is not None else str(e)
            logger.error(
                f"LLM HTTP error after {processing_time:.2f}ms: {e.response.status_code if e.response else 'unknown'} {content}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM HTTP error: {content}",
            )
        except Exception as e:
            processing_time = (time.time() - request_start) * 1000
            logger.exception(
                f"LLM processing failed after {processing_time:.2f}ms: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM call failed: {str(e)}",
            )

    @staticmethod
    async def stream_response(
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> AsyncIterator[str]:
        """
        Stream response deltas from the configured OpenRouter-compatible chat endpoint.

        The public websocket layer consumes these deltas directly, so callers get
        first-token latency instead of post-processing a completed response.
        """
        model_config = get_model_config()
        model = model or model_config.model_name
        temperature = temperature or model_config.temperature
        max_tokens = max_tokens or model_config.max_tokens
        timeout = timeout or model_config.timeout_seconds
        request_start: float = 0.0

        try:
            api_key = LLMService.get_api_key()
            url = LLMService.get_api_url()

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }
            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            httpx_timeout = httpx.Timeout(
                connect=10.0,
                read=float(timeout),
                write=30.0,
                pool=5.0,
            )

            request_start = time.time()
            async with httpx.AsyncClient(timeout=httpx_timeout) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if not line.startswith("data:"):
                            continue

                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break

                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            logger.debug("Skipping malformed LLM stream payload: %s", data[:200])
                            continue

                        choices = payload.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        chunk = delta.get("content")
                        if isinstance(chunk, str) and chunk:
                            yield chunk

            processing_time = (time.time() - request_start) * 1000
            logger.info("LLM response streamed in %.2fms", processing_time)

        except httpx.TimeoutException as e:
            processing_time = (time.time() - request_start) * 1000
            logger.error("LLM stream timeout after %.2fms: %s", processing_time, e)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="LLM request timed out",
            )
        except httpx.HTTPStatusError as e:
            processing_time = (time.time() - request_start) * 1000
            content = e.response.text if e.response is not None else str(e)
            logger.error(
                "LLM stream HTTP error after %.2fms: %s %s",
                processing_time,
                e.response.status_code if e.response else "unknown",
                content,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM HTTP error: {content}",
            )
        except Exception as e:
            processing_time = (time.time() - request_start) * 1000
            logger.exception("LLM streaming failed after %.2fms: %s", processing_time, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM stream failed: {str(e)}",
            )

    @staticmethod
    async def generate_response_with_stored_context(
        db: Session,
        user_id: int,
        github_context: dict = None,
        conversation_history: List[Tuple[str, str]] = None,
        file_contexts: List[str] = None,
        probe_context: Optional[str] = None,
        fallback_repo_summary: Optional[str] = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Generate response using pre-fetched and stored GitHub context with improved error handling

        Args:
            db: Database session (unused but retained for signature compatibility)
            user_id: ID of the user requesting the response
            github_context: Repository/session context dictionary
            conversation_history: Recent conversation turns
            file_contexts: Supplemental repository snippets
            probe_context: Code exploration results returned by sandbox probes.
            fallback_repo_summary: Textual summary from ``ChatContext`` when
                structured context is unavailable.
            model: Override model identifier
            temperature: Override generation temperature
            max_tokens: Maximum tokens for the response
            timeout: API timeout in seconds
        """
        try:
            # Build prompt using centralized prompt building with error handling
            try:
                prompt = LLMService._build_daifu_prompt_from_context(
                    github_context=github_context,
                    conversation=conversation_history or [],
                    file_contexts=file_contexts,
                    probe_context=probe_context,
                    fallback_repo_summary=fallback_repo_summary,
                )
            except Exception as prompt_error:
                logger.warning(f"Failed to build prompt: {prompt_error}")
                # Fallback to simple prompt
                prompt = f"User: {conversation_history[-1][1] if conversation_history else 'Hello'}\nAssistant:"

            # Generate response with error handling
            try:
                raw_response = await LLMService.generate_response(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                parsed = LLMService.format_chat_response_v2(raw_response)
                return {
                    "text": parsed.text,
                    "actions": parsed.actions,
                    "questions": parsed.questions,
                    "probes": parsed.probes,
                    "tool_calls": parsed.tool_calls,
                    "raw_response": raw_response,
                }
            except Exception as generation_error:
                logger.error(f"Failed to generate response: {generation_error}")
                # Return fallback response
                fallback_text = (
                    "I'm having trouble processing your request right now. "
                    "Please try again in a moment."
                )
                return {
                    "text": fallback_text,
                    "actions": [],
                    "questions": [],
                    "probes": [],
                    "tool_calls": [],
                    "raw_response": fallback_text,
                }

        except Exception as e:
            logger.error(f"Failed to generate response with stored context: {e}")
            # Return a helpful fallback response instead of raising an exception
            fallback_text = (
                "I understand you're asking about something, but I'm currently "
                "experiencing technical difficulties. Please try again in a moment."
            )
            return {
                "text": fallback_text,
                "actions": [],
                "questions": [],
                "probes": [],
                "tool_calls": [],
                "raw_response": fallback_text,
            }

    @staticmethod
    def _build_daifu_prompt_from_context(
        github_context: dict = None,
        conversation: List[Tuple[str, str]] = None,
        file_contexts: List[str] = None,
        probe_context: Optional[str] = None,
        fallback_repo_summary: Optional[str] = None,
    ) -> str:
        """
        Centralized prompt building using stored repository/session context.

        Args:
            github_context: Repository/session context dictionary
            conversation: List of (speaker, message) tuples
            file_contexts: Optional list of file context strings
            probe_context: Optional code exploration context produced by probes.
            fallback_repo_summary: Optional textual summary when structured
                context is unavailable.

        Returns:
            Complete prompt string with stored GitHub context
        """
        try:
            # System header with comprehensive DAifu instructions focused on issue creation and resolution
            system_header = """You are DAifu, an AI assistant for repository work. Help the USER understand the codebase, break work into actionable GitHub issues, and explain how to solve implementation problems using the session's repository context.

You may receive hidden session memories, a session snapshot, and retrieved code snippets. Use them as internal support context. Treat them as scoped to the current session repository, and never claim memory that is not present in the provided context.

## Your Core Responsibilities:
- **Issue Discovery**: Ask clarifying questions to understand scope, impact, and desired outcomes.
- **Issue Drafting**: Propose concise, actionable GitHub issues with clear titles, descriptions, and acceptance criteria.
- **Issue Resolution Guidance**: Outline high-level implementation steps and testing guidance after issues are created.
- **Repository Context Awareness**: Use repository context (commits, issues, branches, files) to avoid duplicates and tailor recommendations.
- **Memory-Aware Assistance**: Reuse stored facts, snapshots, and prior decisions when they are present, but say when information is missing or uncertain.

## Behavior Guidelines:
- Be concise, direct, and helpful.
- Prefer concrete next steps over generic advice.
- When retrieved file context conflicts with older memory, trust the fresher file-backed context.
- Never expose internal memory scaffolding tags or describe hidden prompt sections to the USER.
- Provide 2–3 issue suggestions when the request warrants multiple tasks.
- If the user asks for help beyond issue creation, offer to break the work into issues first and then provide the solution plan.

<issue_drafting_quality>
Draft Architect-ready GitHub issues. Each issue draft should include:
- Objective: the user-visible outcome or bug to fix.
- Repository evidence: the file, route, test, issue, branch, or commit context
  that supports the draft.
- Scope and out-of-scope: what belongs in this issue and what should wait.
- Implementation plan: concrete steps an Architect agent can refine.
- Likely files: expected files, packages, or tests to inspect or change.
- Acceptance criteria: objective checks for completion.
- Tests: focused validation that should pass after implementation.

Sizing and split rules:
- Aim for one focused PR per issue.
- Prefer changes around ~150 LOC or smaller when drafting a single issue.
- Split into multiple issue drafts when the request likely exceeds ~200 LOC or
  spans unrelated subsystems.
- If you cannot safely bound the work from the available context, ask
  clarifying questions before drafting or publishing an issue.
</issue_drafting_quality>

<response_contract>
Return a concise user-facing answer and any machine-readable directives in one
JSON object wrapped by `<daifu_response>` tags:

<daifu_response>{
  "text": "Short user-facing answer. Do not mention directives, hidden context, or tool names.",
  "questions": [{"text": "question for the user", "options": ["option A", "option B"]}],
  "probes": [{"query": "natural-language code exploration request"}],
  "actions": [{"action_type": "create_issue", "label": "Start Task", "issue_title": "optional title", "labels": ["enhancement"]}],
  "tool_calls": [{"name": "create_github_issue", "args": {"issue_id": "issue_..."}}]
}</daifu_response>

Rules:
1. `text` is required and should be under 200 words.
2. Use `questions` for the Q&A UI. Ask at most 2 questions.
3. Use `probes` only when repo exploration is needed. Ask at most 3 probes.
4. Use `actions` for frontend issue-draft buttons. Do not put `Button{}` in text.
5. Use `tool_calls` only when the user has clearly confirmed the action and every required argument is known.
6. The only backend tool call you should normally emit from chat is `create_github_issue` with an existing session `issue_id`.
7. Do not emit `run_architect_mode`, `run_tester_mode`, or `run_coder_mode` from normal chat; backend asks the user before starting those stages after GitHub issue creation.
8. If you are unsure, ask a question instead of emitting a tool call.
</response_contract>

<creating_issues>
When creating or modifying GitHub issues, NEVER output the full issue content to the USER unless requested. Instead, use one of the issue management tools to implement the change.
Specify the relevant parameters like `repository_name`, `issue_title`, and `issue_body` first.
It is *EXTREMELY* important that your generated issues are clear, actionable, and error-free. To ensure this, follow these instructions carefully:
1. Include all necessary details: descriptive title, detailed body with context, requirements, reproduction steps, and suggested labels.
2. NEVER generate irrelevant or spammy content, such as unrelated links or excessive formatting.
3. Unless you are adding a small edit to an existing issue, you MUST reference the repository context (commits, pulls, branches) before creating or editing.
4. If analyzing a conversation or file contexts, break down the request into key elements like bugs, features, or enhancements.
5. If you encounter errors in context (e.g., missing data), fix them if obvious or ask the USER for clarification. DO NOT loop more than 3 times on the same issue. On the third attempt, stop and ask the USER what to do next.
6. If the request cannot proceed due to invalid context, address it immediately.
</creating_issues>

<github_management>
Use the provided GitHub context (repository details, commits, issues, branches) as your primary source.
If additional data is needed, use tools to fetch it.
Follow the USER's instructions on any specific repository or issue details. If unfamiliar with a GitHub feature, use web_search to find documentation or examples.
At the end of each iteration (e.g., issue creation or update), suggest next steps like assigning labels, linking to pulls, or closing related issues.
Use the suggestions tool to propose improvements for the repository.
</github_management>

<issue_analysis>
When the USER provides a conversation or requests issue creation, analyze the repository context first.
Pay close attention to details like recent commits, open issues, and branches to avoid duplicates.
Before creating an issue, explain your plan to the USER, referencing context: e.g., related commits, potential labels.
You can break down the request into "bugs", "features", or "tasks" in your explanation.
IMPORTANT: If the request is complex or involves multiple issues, ask and confirm with the USER which aspects to prioritize.
If authentication or additional permissions are needed, ask the USER to provide them.
</issue_analysis>

<clarifying_questions>
When you need more information from the user, add entries to the `questions`
array in the response contract. Options are optional for open-ended questions.
</clarifying_questions>

<code_exploration>
When you want the system to explore the codebase for context, add entries to
the `probes` array in the response contract.
Examples:
  {"query": "how does the authentication middleware connect to the database models?"}
  {"query": "what test files exist for the payment processing module?"}
  {"query": "find the route handlers that serve the /api/sessions endpoints"}
Rules: Max 3 probes per response. Describe WHAT you need, not HOW to find it.
Results appear automatically in your next turn's context.
You can combine Questions and Probes; probes run while the user answers.
</code_exploration>

<mode_stage_tools>
When the USER confirms they want an existing GitHub issue implemented, Daifu can start Modal-backed stage tools in order:
1. run_architect_mode enriches the GitHub issue and shared context.
2. run_tester_mode generates/validates the test branch or test artifacts.
3. run_coder_mode implements against the issue/context/test branch and opens the PR.
Never describe shell commands to the USER; the stage tools run inside the sandbox and stream their own progress.
</mode_stage_tools>

<frontend_browser_check_tool>
Daifu can call run_frontend_browser_check to visually verify or screenshot the frontend in the existing Modal sandbox. Use it only when the USER asks for visual verification, browser checking, UI screenshot inspection, or frontend rendering validation. This is a manual sidecar tool, not a fourth automatic workflow stage.
The tool returns artifact metadata plus a textual visual report. It does not provide direct image input to you in v1.
</frontend_browser_check_tool>

<github_issue_tool>
Daifu can also call create_github_issue to publish an existing drafted user issue to GitHub.
Use it only when an issue_id from the current session is already available; the tool is a thin wrapper over the backend GitHub issue creation function.
After the GitHub issue is created, Daifu asks the USER before starting the Architect -> Tester -> Coder workflow.
</github_issue_tool>

[Final Instructions]
Answer the USER's request through the response contract. Check that all required
parameters for any tool call are known. If required values are missing, ask the
USER through `questions`; do not invent tool arguments. If the USER provides a
specific value for a parameter, use it exactly.

[IMPORTANT]
Reply in the same language as the USER.
On the first prompt, don't create issues until the USER confirms the plan.
If the USER provides ambiguous input, like a single word or phrase, explain how you can help and suggest a few possible ways (e.g., clarifying the bug report, drafting feature issues, or planning issue breakdowns).
If USER asks for tasks outside repository issue creation, explain that you can still help but recommend structuring the work as issues first. Confirm with the USER before proceeding.

# Tools

## functions

namespace functions {

// Fetch detailed repository information.
type get_repository_details = (_: {
repository_name: string, // format: "owner/repo"
}) => any;

// List recent commits.
type list_commits = (_: {
repository_name: string,
branch?: string, // default: "main"
count?: number, // default: 10
}) => any;

// List open issues.
type list_issues = (_: {
repository_name: string,
state?: "open" | "closed" | "all", // default: "open"
count?: number, // default: 10
}) => any;

// List branches.
type list_branches = (_: {
repository_name: string,
count?: number, // default: 10
}) => any;

// Create a new GitHub issue.
type create_issue = (_: {
repository_name: string,
title: string,
body: string,
labels?: string[], // optional array of labels
assignees?: string[], // optional array of assignees
}) => any;

// Publish an existing drafted Daifu user issue to GitHub.
type create_github_issue = (_: {
issue_id: string,
}) => any;

// Visually verify or screenshot the frontend in the existing sandbox.
type run_frontend_browser_check = (_: {
objective: string,
}) => any;

// Search the web for OnchainKit, Base, or GitHub-related information, examples, or best practices.
type web_search = (_: {
search_term: string,
type?: "text" | "images", // default: "text"
}) => any;

} // namespace functions

## multi_tool_use

// This tool serves as a wrapper for utilizing multiple tools. Each tool that can be used must be specified in the tool sections. Only tools in the functions namespace are permitted.
// Ensure that the parameters provided to each tool are valid according to that tool's specification.
namespace multi_tool_use {

// Use this function to run multiple tools simultaneously, but only if they can operate in parallel. Do this even if the prompt suggests using the tools sequentially.
type parallel = (_: {
tool_uses: {
recipient_name: string,
parameters: object,
}[],
}) => any;

} // namespace multi_tool_use"""

            # Format repository details from stored context with error handling
            details_str = "Repository information not available"
            commits_str = "Recent Commits: None available"
            issues_str = "Open Issues: None available"
            branches_str = "Repository Branches: None available"

            try:
                if github_context and isinstance(github_context, dict) and "repository" in github_context:
                    repo = github_context["repository"]

                    # Repository info with safe access
                    details_str = (
                        f"Repository: {repo.get('full_name', 'Unknown')}\n"
                        f"Description: {repo.get('description', '')}\n"
                        f"Default branch: {repo.get('default_branch', 'main')}\n"
                        f"Language: {repo.get('language', '')}\n"
                        f"Stars: {repo.get('stargazers_count', 0)}, Forks: {repo.get('forks_count', 0)}\n"
                        f"Open issues: {repo.get('open_issues_count', 0)}\n"
                        f"URL: {repo.get('html_url', '')}\n"
                    )

                    # Recent commits with error handling
                    try:
                        if (
                            "recent_commits" in github_context
                            and github_context["recent_commits"]
                            and isinstance(github_context["recent_commits"], list)
                        ):
                            commits = github_context["recent_commits"][:3]  # Limit to 3
                            commits_str = "Recent Commits:\n"
                            for commit in commits:
                                if isinstance(commit, dict):
                                    commits_str += f"- {commit.get('sha', '')[:7]}: {commit.get('message', '')[:50]}\n"
                    except Exception as commits_error:
                        logger.warning(f"Error processing commits: {commits_error}")
                        commits_str = "Recent Commits: Error loading\n"

                    # Open issues with error handling
                    try:
                        if (
                            "recent_issues" in github_context
                            and github_context["recent_issues"]
                            and isinstance(github_context["recent_issues"], list)
                        ):
                            issues = github_context["recent_issues"][:3]  # Limit to 3
                            issues_str = "Open Issues:\n"
                            for issue in issues:
                                if isinstance(issue, dict):
                                    issues_str += f"- #{issue.get('number', '?')}: {issue.get('title', '')[:50]}\n"
                    except Exception as issues_error:
                        logger.warning(f"Error processing issues: {issues_error}")
                        issues_str = "Open Issues: Error loading\n"

                    # Branches with error handling
                    try:
                        if "branches" in github_context and github_context["branches"] and isinstance(github_context["branches"], list):
                            branches = github_context["branches"][:3]  # Limit to 3
                            branches_str = "Repository Branches:\n"
                            for branch in branches:
                                if isinstance(branch, dict):
                                    branches_str += f"- {branch.get('name', 'Unknown')}\n"
                    except Exception as branches_error:
                        logger.warning(f"Error processing branches: {branches_error}")
                        branches_str = "Repository Branches: Error loading\n"

                elif fallback_repo_summary:
                    logger.info("Building prompt using fallback repository summary")
                    details_str = fallback_repo_summary.strip()
                    commits_str = "Recent Commits: Not available (cached summary used)"
                    issues_str = "Open Issues: Not available (cached summary used)"
                    branches_str = "Repository Branches: Not available (cached summary used)"

            except Exception as context_error:
                logger.warning(f"Error processing GitHub context: {context_error}")
                # Continue with default values

            # Format support contexts if provided
            probe_section = ""
            if probe_context:
                probe_section = (
                    "\n<CODE_EXPLORATION_BEGIN>\n"
                    f"{probe_context.strip()}\n"
                    "</CODE_EXPLORATION_END>\n"
                )

            file_contexts_str = ""
            if file_contexts:
                file_contexts_str = "Session Support Context:\n" + "\n".join(
                    file_contexts
                )

            # Format conversation
            convo_formatted = ""
            if conversation:
                convo_formatted = "\n".join(
                    f"{speaker}: {utterance}" for speaker, utterance in conversation
                )

            first_response_instruction = ""
            if conversation and len(conversation) <= 1:
                first_response_instruction = (
                    "\n<FIRST_RESPONSE>\n"
                    "This is the first assistant response in a new session. "
                    "Ask 2–4 clarifying questions before proposing issues.\n"
                    "</FIRST_RESPONSE>\n"
                )

            # Combine all into final prompt
            prompt = f"""{system_header}{first_response_instruction}

<GITHUB_CONTEXT_BEGIN>
{details_str}
{commits_str}
{issues_str}
{branches_str}
</GITHUB_CONTEXT_END>
{probe_section}

<SUPPORT_CONTEXT_BEGIN>
{file_contexts_str}
</SUPPORT_CONTEXT_END>

<CONVERSATION_BEGIN>
{convo_formatted}
</CONVERSATION_END>

(Respond now as DAifu following the response contract. Output exactly one `<daifu_response>` JSON block.)"""
            return prompt.strip()

        except Exception as e:
            logger.error(f"Failed to build prompt from context: {e}")
            # Return a simple fallback prompt
            return f"User: {conversation[-1][1] if conversation else 'Hello'}\nAssistant:"
