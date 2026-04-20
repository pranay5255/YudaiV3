# Plan: Hybrid Daifu + Architect Context Probe System

## Context

Daifu (conversational chat agent) streams LLM responses but cannot search the repo. Architect (sandbox agent) can grep/read the full codebase via multi-turn bash tool calls but cannot hold a conversation. The goal: Daifu passes **natural language context queries** to one or more lightweight Architect agents running in the sandbox, and those agents autonomously explore the codebase and return structured context back to Daifu. Daifu never sees or generates shell commands — it only describes what it needs to know.

## Key Design Principle

**Daifu speaks human. Architect speaks bash.** Daifu emits queries like `"how does auth connect with the backend DB?"`. A mini Architect agent receives that as its task, uses `rg`/`find`/`cat`/`git grep` to explore (just like the full Architect does today), and writes its findings to a context file that gets fed back to Daifu's next prompt. Multiple probes can run in parallel for different questions.

---

## Architecture Overview

```
User sends message
    │
    ▼
Daifu streams response
    │
    ▼
Response parsed for directives:
    ├── Question{"which module?"} → sent to user (existing AGENT_QUESTION flow)
    └── Probe{"how auth connects to DB"}  ─┐
        Probe{"what tests exist for auth"} ─┤  (up to 3 parallel probes)
                                            │
                        ┌───────────────────┘
                        ▼
              For each probe, spawn a mini Architect agent:
              `mini -c probe_config.yaml -m model -t "query text"`
              running inside the existing sandbox
                        │
                        ▼ (parallel, 8-step limit, 60s timeout)
              Each agent greps/reads code autonomously
              Writes findings to .yudai/probe_{id}.md
                        │
                        ▼
              Results cached in session.mode_metadata
              ────────────────────────────────────────
              Meanwhile, user is answering questions...
              ────────────────────────────────────────
                        │
    User answers ───────┤
                        ▼
              Next Daifu turn injects:
              - User's answers (from UserQuestion records)
              - Probe results (from cached context files)
              → Rich, code-grounded response
```

---

## New File: `backend/realtime/mswea_mode_configs/probe/config.yaml`

A stripped-down Architect config optimized for fast, focused context gathering:

```yaml
agent:
  system_template: |
    You are a code exploration agent for Yudai. Your job is to quickly find
    and summarize relevant code context for a conversational AI assistant.

    Hard constraints:
    - Do NOT create issues, PRs, or modify any source files.
    - Do NOT write tests or implement changes.
    - You may only READ the repository using search and read commands.
    - Write your findings into the file at `$YUDAI_PROBE_OUTPUT` in markdown.
    - Be concise: include file paths, line numbers, and short code snippets.
    - Focus on answering the specific question, not giving a full repo tour.
    - When done, print your findings as a single JSON object with keys:
      `summary` (1-3 sentences), `files` (list of relevant file paths),
      `snippets` (list of {path, lines, content} objects).
    - Submit by issuing: `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`

  instance_template: |
    Answer this context question by exploring the repository:

    {{task}}

    Workspace: `$WORKSPACE_PATH`
    Write findings to: `$YUDAI_PROBE_OUTPUT`

    Use fast search tools: `rg`, `find`, `git grep`, `head`, `cat`.
    Be thorough but quick — you have limited steps.

    ## Command Execution Rules
    (same as architect config — omitted for brevity, identical block)

  step_limit: 8
  cost_limit: 0.50
  mode: confirm

environment:
  env:
    PAGER: cat
    MANPAGER: cat
    LESS: -R
    PIP_PROGRESS_BAR: 'off'
    TQDM_DISABLE: '1'

model:
  observation_template: |
    (same as architect config)
  format_error_template: |
    (same as architect config)
  model_kwargs:
    drop_params: true
```

**Key differences from Architect config:**
- `step_limit: 8` (vs 40) — fast, focused exploration
- `cost_limit: 0.50` (vs 3.0) — cheap throwaway probes
- System prompt says READ ONLY, no issue creation, no file modification
- Output goes to `$YUDAI_PROBE_OUTPUT` (per-probe file) not `$YUDAI_CONTEXT_FILE`

---

## New File: `backend/daifuUserAgent/context_probe.py`

```python
@dataclass
class ProbeRequest:
    probe_id: str               # f"probe_{uuid4().hex[:10]}"
    query: str                  # natural language: "how does auth connect to DB?"

@dataclass
class ProbeResult:
    probe_id: str
    status: str                 # "completed" | "timeout" | "error" | "no_sandbox"
    output_text: str            # raw markdown from probe output file
    summary: Optional[str]      # parsed from JSON if available
    files: List[str]            # parsed file paths
    duration_ms: int

class ContextProbeService:
    """Spawns lightweight Architect agents in the sandbox for context gathering."""

    PROBE_CONFIG_PATH = "/app/mswea_mode_configs/probe/config.yaml"
    PROBE_TIMEOUT_SECONDS = 60

    def __init__(self, broker: SandboxExecBroker):
        self.broker = broker

    async def run_probe(self, db, *, session, probe: ProbeRequest) -> ProbeResult:
        """Run a single mini Architect agent with the probe query as its task."""
        # Builds a bash command similar to _build_mswea_command() but:
        # - Uses probe/config.yaml instead of architect/config.yaml
        # - Sets YUDAI_PROBE_OUTPUT to .yudai/probes/{probe_id}.md
        # - Task text is just the probe.query (no issue numbers, no context file)
        # - 60s timeout
        # Calls self.broker.run_command(db, session=session, command=cmd, ...)
        # Reads the probe output file from stdout (cat at end of script)
        # Parses JSON summary if present in output

    async def run_probes_parallel(
        self, db, *, session, probes: List[ProbeRequest]
    ) -> List[ProbeResult]:
        """Run up to 3 probes concurrently via asyncio.gather()."""
        tasks = [self.run_probe(db, session=session, probe=p) for p in probes[:3]]
        return await asyncio.gather(*tasks, return_exceptions=True)
        # Wraps exceptions into ProbeResult(status="error")

    @staticmethod
    def format_as_context(results: List[ProbeResult]) -> Optional[str]:
        """Format all probe results into a single context string for Daifu's prompt."""
        # Returns None if all probes failed/empty
        # Format:
        # [CODE_EXPLORATION_CONTEXT]
        # ## Query: "how does auth connect to DB?"
        # {output_text or summary}
        # Files found: path1.py, path2.py
        #
        # ## Query: "what tests exist for auth?"
        # ...

    @staticmethod
    def has_active_sandbox(db, session) -> bool:
        """Quick check: does this session have a reachable sandbox?"""

    def _build_probe_command(self, probe: ProbeRequest, workspace: str) -> str:
        """Build the bash script to run mini with probe config."""
        # Similar structure to mode_orchestrator._build_mswea_command() but:
        # - No git clone/fetch (repo already there from prior pipeline or runtime)
        # - Uses PROBE_CONFIG_PATH
        # - Sets YUDAI_PROBE_OUTPUT env var
        # - Cats the output file at the end so we capture it in stdout
```

**Why a real Architect agent (mini-swe-agent) instead of raw commands:**
- The Architect already knows how to explore a codebase — it decides what to grep, reads results, follows leads across files. A single `rg` call can't do multi-hop reasoning.
- With `step_limit: 8` and `cost_limit: 0.50`, each probe is cheap and fast.
- Reuses the exact same infra (`mini` CLI + config.yaml) — no new execution engine.

---

## Modified Files

### 1. `backend/daifuUserAgent/llm_service.py`

**a) Add directive patterns** (after line 46):
```python
QUESTION_DIRECTIVE_PATTERN = re.compile(
    r'Question\{\s*"(?P<text>[^"]+)"(?:\s+options=\[(?P<options>[^\]]*)\])?\s*\}',
    re.IGNORECASE,
)
PROBE_DIRECTIVE_PATTERN = re.compile(
    r'Probe\{\s*"(?P<query>[^"]+)"\s*\}',
    re.IGNORECASE,
)
```

Note: `Probe{}` only takes a natural language query — no commands. The Architect agent decides what commands to run.

**b) Add `DaifuParsedResponse` dataclass and `format_chat_response_v2()`:**
```python
@dataclass
class DaifuParsedResponse:
    text: str
    actions: List[Dict[str, Any]]       # existing Button{} actions
    questions: List[Dict[str, Any]]     # [{"text": str, "options": [{"id","label"}]}]
    probes: List[Dict[str, Any]]        # [{"query": str}]
```

Parses Question{} and Probe{} directives, strips them from text, keeps backward compat with old `format_chat_response()`.

**c) Add Probe/Question instructions to system prompt** (~line 582, before `[Final Instructions]`):
```
<clarifying_questions>
When you need more information from the user, emit:
  Question{"your question text" options=["option1", "option2"]}
Rules: Max 2 questions per response. Options are optional for open-ended questions.
</clarifying_questions>

<code_exploration>
When you want the system to explore the codebase for context, emit:
  Probe{"natural language description of what you need to know"}
Examples:
  Probe{"how does the authentication middleware connect to the database models?"}
  Probe{"what test files exist for the payment processing module?"}
  Probe{"find the route handlers that serve the /api/sessions endpoints"}
Rules: Max 3 probes per response. Describe WHAT you need, not HOW to find it.
Results appear automatically in your next turn's context.
You can combine Questions and Probes — probes run while the user answers.
</code_exploration>
```

**d) Extend `_build_daifu_prompt_from_context()`** — add `probe_context: Optional[str] = None` parameter:
```python
# Insert between GITHUB_CONTEXT and SUPPORT_CONTEXT sections:
probe_section = ""
if probe_context:
    probe_section = f"\n<CODE_EXPLORATION_BEGIN>\n{probe_context}\n</CODE_EXPLORATION_END>\n"
```

### 2. `backend/daifuUserAgent/ChatOps.py`

**a) Inject cached probe results at context-gathering time** (~line 308):
```python
# After bootstrap context, before file embeddings
probe_context = self._consume_probe_context(session)
if probe_context:
    context_inputs.append(probe_context)
```

New method:
```python
def _consume_probe_context(self, session: ChatSession) -> Optional[str]:
    """Read and clear cached probe results from mode_metadata."""
    meta = session.mode_metadata or {}
    probe_results = meta.get("probe_results")
    if not probe_results:
        return None
    # Clear consumed results
    meta.pop("probe_results", None)
    meta.pop("gathering_state", None)
    meta.pop("pending_probe_ids", None)
    session.mode_metadata = meta
    # Format using ContextProbeService
    from .context_probe import ContextProbeService, ProbeResult
    results = [ProbeResult(**r) for r in probe_results]
    return ContextProbeService.format_as_context(results)
```

**b) After LLM stream, trigger gathering phase** (~line 390):
```python
parsed = LLMService.format_chat_response_v2(raw_response)
ai_response = parsed.text
ai_actions = parsed.actions

if parsed.questions or parsed.probes:
    await self._start_gathering_phase(
        session=session,
        user_id=user_id,
        questions=parsed.questions,
        probes=parsed.probes,
    )
```

**c) New method `_start_gathering_phase()`:**
```python
async def _start_gathering_phase(self, session, user_id, questions, probes):
    ws_hub = get_ws_hub()
    question_ids = []

    # 1. Create UserQuestion records (up to 2)
    for q in questions[:2]:
        uq = UserQuestion(
            question_id=f"q_{uuid.uuid4().hex[:10]}",
            session_id=session.id,
            user_id=user_id,
            question_text=q["text"],
            options=q.get("options", []),
            status="pending",
        )
        self.db.add(uq)
        question_ids.append(uq.question_id)

    # 2. Build probe requests (up to 3)
    probe_requests = []
    for p in probes[:3]:
        probe_requests.append(ProbeRequest(
            probe_id=f"probe_{uuid.uuid4().hex[:10]}",
            query=p["query"],
        ))

    # 3. Update session metadata
    meta = session.mode_metadata or {}
    meta["pending_question_ids"] = question_ids
    meta["pending_probe_ids"] = [p.probe_id for p in probe_requests]
    meta["gathering_state"] = "active"
    session.mode_metadata = meta
    if question_ids:
        session.mode_status = "waiting_for_input"
    self.db.commit()

    # 4. Send questions over WS
    for q_id, q in zip(question_ids, questions[:2]):
        await ws_hub.send_to_session(
            session.session_id,
            WSMessageType.AGENT_QUESTION,
            {"question_id": q_id, "question_text": q["text"],
             "options": q.get("options", [])},
        )

    # 5. Fire probes in background (parallel)
    if probe_requests:
        asyncio.create_task(
            self._run_probes_background(
                session.session_id, session.id, probe_requests
            )
        )
        # Notify frontend that exploration is happening
        await ws_hub.send_to_session(
            session.session_id,
            WSMessageType.STATUS,
            {"status": "exploring_codebase",
             "detail": f"Running {len(probe_requests)} code exploration(s)..."},
        )
```

**d) New method `_run_probes_background()`:**
```python
async def _run_probes_background(self, session_public_id, session_db_id, probes):
    """Run probes in parallel, cache results in mode_metadata."""
    from .context_probe import ContextProbeService
    from realtime.lifecycle import get_sandbox_exec_broker
    from db.database import SessionLocal

    service = ContextProbeService(get_sandbox_exec_broker())
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_db_id).first()
        if not session:
            return

        results = await service.run_probes_parallel(db, session=session, probes=probes)

        # Cache results in mode_metadata
        meta = session.mode_metadata or {}
        meta["probe_results"] = [asdict(r) for r in results if not isinstance(r, Exception)]
        meta.pop("pending_probe_ids", None)

        # Check if questions are also done
        pending_qs = meta.get("pending_question_ids", [])
        if not pending_qs:
            meta["gathering_state"] = "complete"
        else:
            meta["gathering_state"] = "probes_done"  # waiting for user answers

        session.mode_metadata = meta
        db.commit()

        # Notify frontend
        await get_ws_hub().send_to_session(
            session_public_id,
            WSMessageType.STATUS,
            {"status": "exploration_complete",
             "detail": f"{len(results)} exploration(s) finished"},
        )
    finally:
        db.close()
```

### 3. `backend/daifuUserAgent/session_routes.py`

**Modify `answer_session_question()`** (~after line 1446, after marking question answered):
```python
# Update gathering state
meta = session.mode_metadata or {}
pending_qs = meta.get("pending_question_ids", [])
pending_qs = [q for q in pending_qs if q != question_id]
meta["pending_question_ids"] = pending_qs

if not pending_qs:
    # All questions answered
    if meta.get("gathering_state") in ("probes_done", "complete") or not meta.get("pending_probe_ids"):
        meta["gathering_state"] = "complete"
    # else: probes still running, they'll set gathering_state when done
session.mode_metadata = meta
```

### 4. Frontend (minor)

**`src/hooks/useSessionWebSocket.ts`**: Handle `status` events with `exploring_codebase` / `exploration_complete` to set a flag.

**`src/components/Chat.tsx`** (or parent): Show a subtle "Exploring codebase..." indicator alongside the question prompt when flag is set.

---

## Surfaces Where Daifu Calls Architect Probes

| User Says | Daifu Emits | Probe Agent Does |
|-----------|-------------|------------------|
| "I want to fix the auth flow" | `Probe{"find all authentication-related files and their relationships"}` + `Question{"Which auth flow — JWT, OAuth, or session-based?"}` | `rg -l 'auth' backend/` → reads promising files → maps dependencies → writes summary |
| "How does payment processing work?" | `Probe{"trace the payment processing flow from route handler to database"}` | `rg -n 'payment\|billing' --type py` → follows imports → reads key functions → summarizes |
| "What tests cover the session API?" | `Probe{"find all test files for the session management endpoints"}` | `find backend/tests/ -name '*session*'` → reads test files → lists what's covered |
| "Can you break this into issues?" | `Probe{"understand the current state of the feature X implementation"}` + `Probe{"find existing GitHub issues related to feature X"}` | Two parallel agents explore different angles |
| "I got an error in the webhook handler" | `Probe{"find the webhook handler implementation and its error handling"}` + `Question{"Can you paste the error message?"}` | Agent greps for webhook routes while user types the error |

Daifu never knows the directory structure. It just says what it needs. The Architect agent (mini-swe-agent with probe config) autonomously decides how to explore.

---

## How Architect Feeds Context Back to Daifu

1. Each probe agent writes findings to `.yudai/probes/{probe_id}.md` inside the sandbox
2. The probe command script `cat`s this file at the end → captured in `stdout` by `run_sandbox_command()`
3. `ContextProbeService` parses the stdout into `ProbeResult`
4. Results stored in `session.mode_metadata["probe_results"]` as JSON
5. On next `process_chat_message_stream()`, `_consume_probe_context()` reads + clears the cache
6. Formatted as `[CODE_EXPLORATION_CONTEXT]` section injected into Daifu's prompt
7. Daifu responds with code-grounded understanding — can reference specific files, functions, line numbers

---

## Gathering State Machine

```
                  ┌─────────────────────────┐
                  │    gathering_state       │
                  │    = "active"            │
                  │                          │
                  │  pending_question_ids    │
                  │  pending_probe_ids       │
                  └──────┬──────────┬────────┘
                         │          │
            probes finish│          │user answers all questions
                         ▼          ▼
               ┌──────────┐  ┌──────────────┐
               │"probes_  │  │(probes still  │
               │ done"    │  │ running)      │
               └────┬─────┘  └──────┬───────┘
                    │               │
         user answers│        probes finish│
                    ▼               ▼
               ┌────────────────────────┐
               │ gathering_state        │
               │ = "complete"           │
               │                        │
               │ probe_results: [...]   │ ← ready for next Daifu turn
               └────────────────────────┘
```

**Edge cases:**
- No sandbox active → probes skipped, questions-only mode (graceful degradation)
- Probe times out (>60s) → partial output returned, status="timeout", still useful
- User sends new message before probes finish → `_consume_probe_context()` returns None, Daifu responds without; probe results available on the turn after
- All probes fail → `probe_results` is empty list, `format_as_context()` returns None, no code context injected

---

## Independence from Pipeline

This system is **completely independent** from the Architect→Tester→Coder pipeline:
- Uses `SandboxExecBroker.run_command()` directly (same as pipeline does)
- Uses a separate config file (`probe/config.yaml` vs `architect/config.yaml`)
- Writes to `.yudai/probes/` not `.yudai/context.md`
- Does not touch `session.current_mode`, `architect_completed_at`, or any pipeline state
- The full pipeline can still be triggered separately for issue resolution

Only requirement: the session must have an active sandbox runtime (provisioned by a prior pipeline start or explicit runtime creation).

---

## Verification Plan

1. **Unit tests**: `format_chat_response_v2()` — parse Question{} and Probe{} directives correctly
2. **Unit tests**: `ContextProbeService.format_as_context()` — formatting, truncation, empty handling
3. **Unit tests**: `_consume_probe_context()` — read-and-clear from mode_metadata
4. **Integration test**: Mock `SandboxExecBroker.run_command()` → verify probe spawns with correct config path and task text, results cached
5. **Integration test**: Full gathering flow — LLM emits Question+Probe → question created → probe runs → user answers → next turn gets both
6. **Config test**: Validate `probe/config.yaml` is valid MSWEA config with correct step_limit
7. **Manual E2E**: Session with active sandbox → send message triggering exploration → verify probes run → answer question → verify next response references code

---

## Files Summary

| Action | File | What |
|--------|------|------|
| **Create** | `backend/realtime/mswea_mode_configs/probe/config.yaml` | Slim Architect config (8 steps, read-only, $0.50 cap) |
| **Create** | `backend/daifuUserAgent/context_probe.py` | ContextProbeService, ProbeRequest/Result, command builder |
| **Modify** | `backend/daifuUserAgent/llm_service.py` | Add directive patterns, `DaifuParsedResponse`, prompt instructions, probe_context param |
| **Modify** | `backend/daifuUserAgent/ChatOps.py` | `_consume_probe_context()`, `_start_gathering_phase()`, `_run_probes_background()` |
| **Modify** | `backend/daifuUserAgent/session_routes.py` | Update gathering state in answer endpoint |
| **Modify** | `src/hooks/useSessionWebSocket.ts` | Handle exploration status events |
| **Modify** | `src/components/Chat.tsx` | Show "Exploring codebase..." indicator |
