# YudaiV3 3-Mode Agent System Implementation Plan

**Date**: 2026-02-27
**Status**: Planning
**Architecture**: Controller + Modal Sandbox + Sessions API + 3-Mode MSWEA Execution

---

## Executive Summary

This document outlines the implementation plan for YudaiV3's new 3-mode agent system that executes:
1. **Architect Mode**: Creates detailed GitHub issues
2. **Tester Mode**: Writes tests for the issue
3. **Coder Mode**: Implements solution, passes tests, creates PR

The system uses the existing MSWEA solver with different configs for each mode, executed within a persistent Modal sandbox.

---

## Architecture Overview

### Current State (from e2e-controller-sessions-modal-report.html)
- Controller host with Sessions API at `/daifu/*`
- Controller lifecycle/proxy routes at `/controller/*`
- Modal provisioning for sandboxes
- MSWEA solver at `backend/solver/mswea/`
- Frontend WS connection via `src/hooks/useSessionWebSocket.ts`
- TrajectoryViewer at `src/components/TrajectoryViewer.tsx`

### New Architecture Components

```
User (Frontend)
    ↓ (Natural Language + Repo Selection)
Controller (Sessions API)
    ↓ (Provisions Modal Sandbox at session creation)
    ↓ (Establishes WS connection)
Modal Sandbox
    ↓ (Clone repo, install MSWEA, create mode configs)
    ↓ (Execute MSWEA with mode configs)
    ↓ (Stream progress via WS)
Controller
    ↓ (Forward WS messages to Frontend)
    ↓ (Orchestrate mode transitions)
Frontend (TrajectoryViewer)
    ↓ (Display 3 sequential phases)
```

---

## Session Flow

### Phase 1: Session Creation & Sandbox Provisioning

1. **User**: Authenticates with GitHub (existing)
2. **Frontend**: User selects repo/branch (existing in `src/`)
3. **Frontend → Controller**: `POST /daifu/sessions` with:
   ```json
   {
     "title": "Implement user authentication",
     "repo_url": "https://github.com/user/repo",
     "branch": "main",
     "github_token": "ghp_xxx"
   }
   ```
4. **Controller**:
   - Creates `ChatSession` in DB with `current_mode: "pending"`
   - Provisions Modal sandbox:
     ```python
     sb = modal.Sandbox.create(
         app=my_app,
         image=sandbox_image,  # includes MSWEA, Python, Git
         timeout=3600,
     )
     ```
   - Executes sandbox initialization:
     ```python
     # Clone repo
     sb.exec("git", "clone", "-b", branch, repo_url, "/workspace/repo", timeout=60)

     # Create mode configs
     sb.exec("python", "-c", f"create_architect_config()", timeout=10)
     sb.exec("python", "-c", f"create_tester_config()", timeout=10)
     sb.exec("python", "-c", f"create_coder_config()", timeout=10)
     ```
   - Establishes WS connection to sandbox (or sandbox establishes WS to controller)
5. **Controller → Frontend**: Returns session ID and WS URL
6. **Frontend**: Connects to controller WS at `/controller/proxy/sessions/{id}/ws/unified`

### Phase 2: Architect Mode (Issue Creation)

7. **User → Frontend**: Sends first natural language message:
   ```
   "Create a login feature with email and password"
   ```
8. **Frontend → Controller**: `POST /daifu/sessions/{id}/messages` with user message
9. **Controller**:
   - Streams conversational response to user (if clarification needed via MCQ)
   - Updates DB: `current_mode: "architect"`
   - Triggers Architect mode in sandbox:
     ```python
     process = sb.exec(
         "python", "-m", "mswea.solve",
         "--config", "/workspace/configs/architect.json",
         "--yolo-mode",
         "--prompt", user_message,
         timeout=600,
     )
     for line in process.stdout:
         # Stream to controller WS
         send_ws_message({"type": "architect_progress", "line": line})
     ```
10. **Sandbox (Architect Mode)**:
    - Analyzes user request
    - Researches codebase
    - Creates detailed GitHub issue with:
      - Title
      - Description
      - Acceptance criteria
      - Technical approach
    - Returns issue URL: `https://github.com/user/repo/issues/123`
11. **Sandbox → Controller**: WS message:
    ```json
    {
      "type": "architect_complete",
      "mode": "architect",
      "issue_url": "https://github.com/user/repo/issues/123",
      "issue_number": 123
    }
    ```
12. **Controller**:
    - Updates DB: `architect_issue_url`, `architect_completed_at`
    - **Auto-triggers Tester mode**

### Phase 3: Tester Mode (Test Creation)

13. **Controller**:
    - Updates DB: `current_mode: "tester"`
    - Triggers Tester mode in sandbox:
      ```python
      process = sb.exec(
          "python", "-m", "mswea.solve",
          "--config", "/workspace/configs/tester.json",
          "--yolo-mode",
          "--issue-number", "123",
          timeout=600,
      )
      ```
14. **Sandbox (Tester Mode)**:
    - Reads GitHub issue #123
    - Analyzes requirements
    - Writes comprehensive tests:
      - Unit tests
      - Integration tests
      - Edge cases
    - Commits tests to branch: `yudai/issue-123-tests`
    - Returns test summary
15. **Sandbox → Controller**: WS message:
    ```json
    {
      "type": "tester_complete",
      "mode": "tester",
      "tests_created": 15,
      "test_branch": "yudai/issue-123-tests"
    }
    ```
16. **Controller**:
    - Updates DB: `tester_status: "complete"`, `tester_completed_at`
    - **Auto-triggers Coder mode**

### Phase 4: Coder Mode (Implementation & PR)

17. **Controller**:
    - Updates DB: `current_mode: "coder"`
    - Triggers Coder mode in sandbox:
      ```python
      process = sb.exec(
          "python", "-m", "mswea.solve",
          "--config", "/workspace/configs/coder.json",
          "--yolo-mode",
          "--issue-number", "123",
          "--test-branch", "yudai/issue-123-tests",
          timeout=1800,
      )
      ```
18. **Sandbox (Coder Mode)**:
    - Reads GitHub issue #123
    - Merges test branch
    - Implements solution
    - Runs tests until all pass
    - Creates GitHub PR:
      - Title: "Fix #123: Implement login feature"
      - Description: Links to issue, describes implementation
      - Branch: `yudai/issue-123-impl`
    - Returns PR URL: `https://github.com/user/repo/pull/456`
19. **Sandbox → Controller**: WS message:
    ```json
    {
      "type": "coder_complete",
      "mode": "coder",
      "pr_url": "https://github.com/user/repo/pull/456",
      "pr_number": 456,
      "tests_passed": true
    }
    ```
20. **Controller**:
    - Updates DB: `coder_pr_url`, `current_mode: "complete"`, `completed_at`
    - Terminates sandbox:
      ```python
      sb.terminate()
      sb.detach()
      ```
21. **Controller → Frontend**: Final WS message:
    ```json
    {
      "type": "session_complete",
      "issue_url": "https://github.com/user/repo/issues/123",
      "pr_url": "https://github.com/user/repo/pull/456"
    }
    ```

---

## Implementation Tasks

### Backend Tasks

#### 1. Database Schema Changes

**File**: `backend/models.py`

**Add to `ChatSession` table**:
```python
# Mode tracking
current_mode = Column(String, default="pending")  # pending, architect, tester, coder, complete
architect_issue_url = Column(String, nullable=True)
architect_completed_at = Column(DateTime(timezone=True), nullable=True)
tester_status = Column(String, nullable=True)  # complete, failed
tester_completed_at = Column(DateTime(timezone=True), nullable=True)
coder_pr_url = Column(String, nullable=True)
coder_completed_at = Column(DateTime(timezone=True), nullable=True)
repo_url = Column(String, nullable=True)
branch = Column(String, nullable=True)
github_token = Column(String, nullable=True)  # encrypted
```

**Create new `AgentExecution` table**:
```python
class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    mode = Column(String, nullable=False)  # architect, tester, coder
    status = Column(String, default="running")  # running, complete, failed
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    output_summary = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)

    session = relationship("ChatSession", back_populates="executions")
```

**Migration**:
```bash
alembic revision --autogenerate -m "Add 3-mode agent tracking"
alembic upgrade head
```

#### 2. Modify Session Creation to Provision Sandbox

**File**: `backend/daifuUserAgent/session_routes.py`

**Modify `POST /daifu/sessions`**:
```python
@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create session in DB
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=request.title,
        repo_url=request.repo_url,
        branch=request.branch or "main",
        github_token=encrypt(request.github_token),  # Store encrypted
        current_mode="pending",
    )
    db.add(session)
    db.commit()

    # Provision Modal sandbox if enabled
    if REALTIME_MODAL_PROVISIONING_ENABLED:
        from backend.realtime.lifecycle import provision_sandbox_for_session
        sandbox_id = await provision_sandbox_for_session(
            session_id=session.id,
            repo_url=session.repo_url,
            branch=session.branch,
            github_token=request.github_token,
        )
        session.sandbox_id = sandbox_id
        db.commit()

    return SessionResponse.from_orm(session)
```

#### 3. Create Sandbox Provisioning with Repo Setup

**File**: `backend/realtime/lifecycle.py`

**Add function**:
```python
async def provision_sandbox_for_session(
    session_id: str,
    repo_url: str,
    branch: str,
    github_token: str,
) -> str:
    """
    Provisions a Modal sandbox for a session with:
    - Repo cloning
    - MSWEA installation
    - Mode config creation
    """
    from backend.realtime.modal_sandbox import RealtimeModalSandbox

    sandbox = await RealtimeModalSandbox.create(
        session_id=session_id,
        repo_url=repo_url,
        branch=branch,
        github_token=github_token,
    )

    sandbox_id = sandbox.id

    # Initialize sandbox
    await sandbox.initialize_workspace()

    return sandbox_id
```

**File**: `backend/realtime/modal_sandbox.py`

**Modify `RealtimeModalSandbox.create()`**:
```python
@classmethod
async def create(
    cls,
    session_id: str,
    repo_url: str,
    branch: str,
    github_token: str,
) -> "RealtimeModalSandbox":
    """Creates and initializes a Modal sandbox with repo and MSWEA."""

    # Create Modal sandbox
    sb = modal.Sandbox.create(
        app=get_modal_app(),
        image=get_sandbox_image(),  # includes Python, Git, MSWEA
        timeout=3600,
        secrets=[modal.Secret.from_name("yudai-secrets")],
    )

    sandbox_id = f"sb-{session_id[:8]}"

    # Store in registry
    RealtimeModalSandboxRegistry.register(
        sandbox_id=sandbox_id,
        modal_sandbox=sb,
        session_id=session_id,
    )

    instance = cls(
        sandbox_id=sandbox_id,
        session_id=session_id,
        modal_sandbox=sb,
        repo_url=repo_url,
        branch=branch,
        github_token=github_token,
    )

    return instance

async def initialize_workspace(self):
    """Clone repo, install MSWEA, create mode configs."""

    # Clone repo
    process = self.modal_sandbox.exec(
        "git", "clone", "-b", self.branch, self.repo_url, "/workspace/repo",
        timeout=120,
    )
    stdout = process.stdout.read()
    if process.returncode != 0:
        raise Exception(f"Failed to clone repo: {stdout}")

    # Install MSWEA (if not in image)
    # Assuming MSWEA is pre-installed in Modal image

    # Create mode configs
    await self.create_mode_configs()

async def create_mode_configs(self):
    """Creates architect.json, tester.json, coder.json in sandbox."""

    architect_config = {
        "mode": "architect",
        "yolo": True,
        "task": "analyze_and_create_issue",
        "tools": ["github_api", "codebase_search", "issue_creator"],
        "max_iterations": 10,
    }

    tester_config = {
        "mode": "tester",
        "yolo": True,
        "task": "write_comprehensive_tests",
        "tools": ["github_api", "test_generator", "pytest"],
        "max_iterations": 15,
    }

    coder_config = {
        "mode": "coder",
        "yolo": True,
        "task": "implement_and_test",
        "tools": ["github_api", "code_editor", "test_runner", "pr_creator"],
        "max_iterations": 30,
    }

    # Write configs to sandbox
    for config_name, config_data in [
        ("architect", architect_config),
        ("tester", tester_config),
        ("coder", coder_config),
    ]:
        config_json = json.dumps(config_data, indent=2)
        self.modal_sandbox.exec(
            "bash", "-c",
            f"echo '{config_json}' > /workspace/configs/{config_name}.json",
            timeout=5,
        )
```

#### 4. Create Mode Orchestrator

**File**: `backend/solver/mode_orchestrator.py` (NEW)

```python
"""
3-Mode Agent System Orchestrator
Manages Architect → Tester → Coder execution flow
"""

import asyncio
from typing import Optional
from backend.realtime.modal_sandbox import RealtimeModalSandboxRegistry
from backend.models import ChatSession, AgentExecution
from backend.database import get_db
from datetime import datetime, timezone


class ModeOrchestrator:
    """Orchestrates 3-mode MSWEA execution in Modal sandbox."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.sandbox = RealtimeModalSandboxRegistry.get(session_id)

    async def execute_architect_mode(self, user_prompt: str) -> dict:
        """
        Execute Architect mode: analyze prompt and create GitHub issue.

        Returns:
            {
                "issue_url": "https://github.com/user/repo/issues/123",
                "issue_number": 123
            }
        """
        # Update DB
        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.current_mode = "architect"
            db.commit()

            # Create execution record
            execution = AgentExecution(
                id=f"exec-arch-{self.session_id[:8]}",
                session_id=self.session_id,
                mode="architect",
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(execution)
            db.commit()

        # Execute in sandbox
        process = self.sandbox.modal_sandbox.exec(
            "python", "-m", "mswea.solve",
            "--config", "/workspace/configs/architect.json",
            "--yolo-mode",
            "--prompt", user_prompt,
            "--workspace", "/workspace/repo",
            timeout=600,
        )

        # Stream output
        output_lines = []
        for line in process.stdout:
            output_lines.append(line)
            # TODO: Send via WS to frontend
            await self.send_ws_progress({
                "type": "architect_progress",
                "line": line.decode() if isinstance(line, bytes) else line,
            })

        # Parse result (assuming MSWEA outputs JSON at end)
        result = self.parse_mswea_output(output_lines)

        # Update DB
        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.architect_issue_url = result["issue_url"]
            session.architect_completed_at = datetime.now(timezone.utc)

            execution = db.query(AgentExecution).filter_by(
                session_id=self.session_id,
                mode="architect"
            ).first()
            execution.status = "complete"
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_summary = result

            db.commit()

        return result

    async def execute_tester_mode(self, issue_number: int) -> dict:
        """
        Execute Tester mode: write tests for the issue.

        Returns:
            {
                "tests_created": 15,
                "test_branch": "yudai/issue-123-tests"
            }
        """
        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.current_mode = "tester"
            db.commit()

            execution = AgentExecution(
                id=f"exec-test-{self.session_id[:8]}",
                session_id=self.session_id,
                mode="tester",
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(execution)
            db.commit()

        process = self.sandbox.modal_sandbox.exec(
            "python", "-m", "mswea.solve",
            "--config", "/workspace/configs/tester.json",
            "--yolo-mode",
            "--issue-number", str(issue_number),
            "--workspace", "/workspace/repo",
            timeout=600,
        )

        output_lines = []
        for line in process.stdout:
            output_lines.append(line)
            await self.send_ws_progress({
                "type": "tester_progress",
                "line": line.decode() if isinstance(line, bytes) else line,
            })

        result = self.parse_mswea_output(output_lines)

        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.tester_status = "complete"
            session.tester_completed_at = datetime.now(timezone.utc)

            execution = db.query(AgentExecution).filter_by(
                session_id=self.session_id,
                mode="tester"
            ).first()
            execution.status = "complete"
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_summary = result

            db.commit()

        return result

    async def execute_coder_mode(self, issue_number: int, test_branch: str) -> dict:
        """
        Execute Coder mode: implement solution and create PR.

        Returns:
            {
                "pr_url": "https://github.com/user/repo/pull/456",
                "pr_number": 456,
                "tests_passed": True
            }
        """
        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.current_mode = "coder"
            db.commit()

            execution = AgentExecution(
                id=f"exec-code-{self.session_id[:8]}",
                session_id=self.session_id,
                mode="coder",
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(execution)
            db.commit()

        process = self.sandbox.modal_sandbox.exec(
            "python", "-m", "mswea.solve",
            "--config", "/workspace/configs/coder.json",
            "--yolo-mode",
            "--issue-number", str(issue_number),
            "--test-branch", test_branch,
            "--workspace", "/workspace/repo",
            timeout=1800,
        )

        output_lines = []
        for line in process.stdout:
            output_lines.append(line)
            await self.send_ws_progress({
                "type": "coder_progress",
                "line": line.decode() if isinstance(line, bytes) else line,
            })

        result = self.parse_mswea_output(output_lines)

        with next(get_db()) as db:
            session = db.query(ChatSession).filter_by(id=self.session_id).first()
            session.coder_pr_url = result["pr_url"]
            session.coder_completed_at = datetime.now(timezone.utc)
            session.current_mode = "complete"
            session.completed_at = datetime.now(timezone.utc)

            execution = db.query(AgentExecution).filter_by(
                session_id=self.session_id,
                mode="coder"
            ).first()
            execution.status = "complete"
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_summary = result

            db.commit()

        # Terminate sandbox
        self.sandbox.modal_sandbox.terminate()
        self.sandbox.modal_sandbox.detach()

        return result

    async def run_full_pipeline(self, user_prompt: str):
        """Run all 3 modes sequentially: Architect → Tester → Coder."""

        # Architect mode
        architect_result = await self.execute_architect_mode(user_prompt)
        await self.send_ws_progress({
            "type": "architect_complete",
            "result": architect_result,
        })

        # Tester mode
        tester_result = await self.execute_tester_mode(architect_result["issue_number"])
        await self.send_ws_progress({
            "type": "tester_complete",
            "result": tester_result,
        })

        # Coder mode
        coder_result = await self.execute_coder_mode(
            architect_result["issue_number"],
            tester_result["test_branch"],
        )
        await self.send_ws_progress({
            "type": "coder_complete",
            "result": coder_result,
        })

        # Final completion
        await self.send_ws_progress({
            "type": "session_complete",
            "issue_url": architect_result["issue_url"],
            "pr_url": coder_result["pr_url"],
        })

    async def send_ws_progress(self, message: dict):
        """Send progress update via WebSocket to frontend."""
        # TODO: Implement WS message sending
        # Use existing WS infrastructure from sandbox_routes.py
        from backend.realtime.ws_protocol import broadcast_to_session
        await broadcast_to_session(self.session_id, message)

    def parse_mswea_output(self, output_lines: list) -> dict:
        """Parse MSWEA output to extract structured result."""
        # TODO: Define MSWEA output format
        # For now, assume last line is JSON
        last_line = output_lines[-1]
        if isinstance(last_line, bytes):
            last_line = last_line.decode()
        return json.loads(last_line)
```

#### 5. Create Message Handler to Trigger Modes

**File**: `backend/daifuUserAgent/session_routes.py`

**Modify `POST /daifu/sessions/{id}/messages`**:
```python
@router.post("/sessions/{session_id}/messages")
async def create_message(
    session_id: str,
    request: MessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Save message to DB
    message = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=request.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.commit()

    # Check if this is the first user message
    session = db.query(ChatSession).filter_by(id=session_id).first()
    message_count = db.query(ChatMessage).filter_by(
        session_id=session_id,
        role="user"
    ).count()

    if message_count == 1 and session.current_mode == "pending":
        # Trigger 3-mode pipeline
        from backend.solver.mode_orchestrator import ModeOrchestrator

        orchestrator = ModeOrchestrator(session_id)

        # Run in background task
        asyncio.create_task(orchestrator.run_full_pipeline(request.content))

        return {
            "message": "Agent pipeline started",
            "status": "processing"
        }

    # Otherwise, handle as normal conversation
    return await handle_conversational_message(session_id, request.content, db)
```

#### 6. Create Conversational API for MCQ/Questions

**File**: `backend/daifuUserAgent/session_routes.py`

**Add new endpoint**:
```python
@router.post("/sessions/{session_id}/ask-question")
async def ask_user_question(
    session_id: str,
    request: AskQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a multiple-choice or multi-select question to the user.

    Request body:
    {
      "question": "Which authentication method should we use?",
      "options": [
        {"label": "JWT", "value": "jwt"},
        {"label": "Session cookies", "value": "session"},
        {"label": "OAuth", "value": "oauth"}
      ],
      "multi_select": false
    }
    """
    # Store question in DB for tracking
    question = UserQuestion(
        id=str(uuid.uuid4()),
        session_id=session_id,
        question_text=request.question,
        options=request.options,
        multi_select=request.multi_select,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(question)
    db.commit()

    # Send via WS to frontend
    from backend.realtime.ws_protocol import broadcast_to_session
    await broadcast_to_session(session_id, {
        "type": "user_question",
        "question_id": question.id,
        "question": request.question,
        "options": request.options,
        "multi_select": request.multi_select,
    })

    return {"question_id": question.id, "status": "sent"}

@router.post("/sessions/{session_id}/questions/{question_id}/answer")
async def answer_question(
    session_id: str,
    question_id: str,
    request: AnswerQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    User answers a question.

    Request body:
    {
      "answer": "jwt"  # or ["jwt", "oauth"] for multi-select
    }
    """
    question = db.query(UserQuestion).filter_by(id=question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.answer = request.answer
    question.status = "answered"
    question.answered_at = datetime.now(timezone.utc)
    db.commit()

    # Resume agent execution with answer
    # TODO: Implement resume logic

    return {"status": "answer_recorded"}
```

### Frontend Tasks

#### 7. Modify TrajectoryViewer for 3 Sequential Phases

**File**: `src/components/TrajectoryViewer.tsx`

**Add phase indicators**:
```tsx
interface PhaseStatus {
  mode: 'architect' | 'tester' | 'coder';
  status: 'pending' | 'running' | 'complete' | 'failed';
  startedAt?: Date;
  completedAt?: Date;
  output?: any;
}

export const TrajectoryViewer: React.FC = () => {
  const [phases, setPhases] = useState<PhaseStatus[]>([
    { mode: 'architect', status: 'pending' },
    { mode: 'tester', status: 'pending' },
    { mode: 'coder', status: 'pending' },
  ]);

  const [currentPhase, setCurrentPhase] = useState<number>(0);

  // Listen to WS messages
  useEffect(() => {
    const handleWSMessage = (message: any) => {
      if (message.type === 'architect_progress') {
        setPhases(prev => {
          const updated = [...prev];
          updated[0].status = 'running';
          return updated;
        });
      } else if (message.type === 'architect_complete') {
        setPhases(prev => {
          const updated = [...prev];
          updated[0].status = 'complete';
          updated[0].output = message.result;
          return updated;
        });
        setCurrentPhase(1);
      } else if (message.type === 'tester_progress') {
        setPhases(prev => {
          const updated = [...prev];
          updated[1].status = 'running';
          return updated;
        });
      } else if (message.type === 'tester_complete') {
        setPhases(prev => {
          const updated = [...prev];
          updated[1].status = 'complete';
          updated[1].output = message.result;
          return updated;
        });
        setCurrentPhase(2);
      } else if (message.type === 'coder_progress') {
        setPhases(prev => {
          const updated = [...prev];
          updated[2].status = 'running';
          return updated;
        });
      } else if (message.type === 'coder_complete') {
        setPhases(prev => {
          const updated = [...prev];
          updated[2].status = 'complete';
          updated[2].output = message.result;
          return updated;
        });
      }
    };

    // Subscribe to WS
    // ... existing WS subscription code
  }, []);

  return (
    <div className="trajectory-viewer">
      <PhaseIndicator phases={phases} currentPhase={currentPhase} />

      <div className="phase-content">
        {phases[currentPhase].status === 'running' && (
          <StreamingOutput phase={phases[currentPhase].mode} />
        )}
        {phases[currentPhase].status === 'complete' && (
          <PhaseResult phase={phases[currentPhase]} />
        )}
      </div>
    </div>
  );
};

const PhaseIndicator: React.FC<{phases: PhaseStatus[], currentPhase: number}> = ({
  phases,
  currentPhase
}) => {
  return (
    <div className="phase-indicator">
      {phases.map((phase, index) => (
        <div
          key={phase.mode}
          className={`phase-step ${phase.status} ${index === currentPhase ? 'active' : ''}`}
        >
          <div className="phase-icon">
            {phase.status === 'complete' ? '✓' :
             phase.status === 'running' ? '⟳' :
             index + 1}
          </div>
          <div className="phase-label">
            {phase.mode.charAt(0).toUpperCase() + phase.mode.slice(1)}
          </div>
        </div>
      ))}
    </div>
  );
};
```

#### 8. Add MCQ/Question UI Components

**File**: `src/components/UserQuestionPrompt.tsx` (NEW)

```tsx
interface UserQuestionProps {
  question: string;
  options: Array<{label: string; value: string}>;
  multiSelect: boolean;
  onAnswer: (answer: string | string[]) => void;
}

export const UserQuestionPrompt: React.FC<UserQuestionProps> = ({
  question,
  options,
  multiSelect,
  onAnswer
}) => {
  const [selected, setSelected] = useState<string[]>([]);

  const handleSubmit = () => {
    if (multiSelect) {
      onAnswer(selected);
    } else {
      onAnswer(selected[0]);
    }
  };

  return (
    <div className="user-question-prompt">
      <h3>{question}</h3>
      <div className="options">
        {options.map(option => (
          <label key={option.value} className="option">
            <input
              type={multiSelect ? 'checkbox' : 'radio'}
              name="question-answer"
              value={option.value}
              checked={selected.includes(option.value)}
              onChange={(e) => {
                if (multiSelect) {
                  setSelected(prev =>
                    e.target.checked
                      ? [...prev, option.value]
                      : prev.filter(v => v !== option.value)
                  );
                } else {
                  setSelected([option.value]);
                }
              }}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      <button onClick={handleSubmit} disabled={selected.length === 0}>
        Submit Answer
      </button>
    </div>
  );
};
```

### Database Tasks

#### 9. Create Migration

**File**: `backend/alembic/versions/xxx_add_3mode_tracking.py` (AUTO-GENERATED)

Run:
```bash
cd backend
alembic revision --autogenerate -m "Add 3-mode agent tracking fields and AgentExecution table"
alembic upgrade head
```

---

## Testing Strategy

### Unit Tests

1. **Test Mode Orchestrator**:
   - `test_execute_architect_mode()`
   - `test_execute_tester_mode()`
   - `test_execute_coder_mode()`
   - `test_run_full_pipeline()`

2. **Test Sandbox Initialization**:
   - `test_clone_repo()`
   - `test_create_mode_configs()`

3. **Test WS Message Handling**:
   - `test_send_architect_progress()`
   - `test_send_tester_complete()`
   - `test_send_session_complete()`

### Integration Tests

1. **Test Full Flow (Mock Modal)**:
   - Create session → provision sandbox → send message → architect → tester → coder → complete

2. **Test Conversational API**:
   - Ask question → receive answer → resume execution

### E2E Tests

1. **Test with Real Modal Sandbox**:
   - Use test repo
   - Verify issue creation
   - Verify test creation
   - Verify PR creation

---

## Configuration Files

### Backend Environment Variables

**File**: `backend/.env.development`

```env
# Existing vars...

# 3-Mode System
MSWEA_ARCHITECT_MAX_ITERATIONS=10
MSWEA_TESTER_MAX_ITERATIONS=15
MSWEA_CODER_MAX_ITERATIONS=30
MODAL_SANDBOX_TIMEOUT=3600
```

### MSWEA Mode Configs (Created in Sandbox)

These are created dynamically in the sandbox at provisioning time.

**File**: `/workspace/configs/architect.json` (in sandbox)

```json
{
  "mode": "architect",
  "yolo": true,
  "task": "analyze_and_create_issue",
  "tools": [
    "github_api",
    "codebase_search",
    "issue_creator",
    "claude_api"
  ],
  "max_iterations": 10,
  "prompts": {
    "system": "You are an expert software architect. Analyze the user's request and create a detailed GitHub issue with clear acceptance criteria.",
    "output_format": "json"
  }
}
```

**File**: `/workspace/configs/tester.json` (in sandbox)

```json
{
  "mode": "tester",
  "yolo": true,
  "task": "write_comprehensive_tests",
  "tools": [
    "github_api",
    "test_generator",
    "pytest",
    "claude_api"
  ],
  "max_iterations": 15,
  "prompts": {
    "system": "You are an expert test engineer. Write comprehensive unit and integration tests for the given issue.",
    "output_format": "json"
  }
}
```

**File**: `/workspace/configs/coder.json` (in sandbox)

```json
{
  "mode": "coder",
  "yolo": true,
  "task": "implement_and_test",
  "tools": [
    "github_api",
    "code_editor",
    "test_runner",
    "pr_creator",
    "claude_api"
  ],
  "max_iterations": 30,
  "prompts": {
    "system": "You are an expert software engineer. Implement the solution for the given issue and ensure all tests pass before creating a PR.",
    "output_format": "json"
  }
}
```

---

## Rollout Plan

### Phase 1: Foundation (Week 1)
- [ ] Database schema changes
- [ ] Sandbox provisioning with repo cloning
- [ ] Mode config creation in sandbox
- [ ] Basic mode orchestrator

### Phase 2: Architect Mode (Week 2)
- [ ] Architect mode execution
- [ ] Issue creation integration
- [ ] WS streaming for architect progress
- [ ] Frontend phase indicator

### Phase 3: Tester & Coder Modes (Week 3-4)
- [ ] Tester mode execution
- [ ] Test creation and branch management
- [ ] Coder mode execution
- [ ] PR creation integration
- [ ] Full pipeline orchestration

### Phase 4: Conversational System (Week 5)
- [ ] Ask question API
- [ ] Answer question API
- [ ] Frontend MCQ UI
- [ ] Resume execution after answer

### Phase 5: Testing & Polish (Week 6)
- [ ] Unit tests
- [ ] Integration tests
- [ ] E2E tests with real Modal
- [ ] Error handling
- [ ] UI polish

---

## Open Questions

1. **MSWEA Integration**: How exactly does MSWEA's "YOLO mode" work? What's the CLI interface?
2. **GitHub Token Security**: Should we encrypt tokens in DB? How to pass securely to sandbox?
3. **Error Handling**: What happens if Architect mode fails? Can user retry? Can they skip to Tester manually?
4. **Multi-Repo Support**: Can users run multiple sessions with different repos simultaneously?
5. **Sandbox Persistence**: Should we allow users to reconnect to sandbox for debugging after completion?
6. **Cost Management**: How to limit Modal sandbox runtime to prevent runaway costs?

---

## Success Criteria

- [ ] User can create session with repo URL
- [ ] Sandbox is provisioned with repo cloned
- [ ] User sends natural language request
- [ ] Architect mode creates GitHub issue
- [ ] Tester mode creates tests in branch
- [ ] Coder mode implements solution and creates PR
- [ ] Frontend shows 3 phases with progress
- [ ] All modes stream output to frontend
- [ ] Session completes and sandbox terminates
- [ ] Database tracks all execution stages

---

## Notes

- This plan assumes MSWEA can be invoked with custom configs via CLI
- WS protocol needs to be extended to support new message types
- Frontend TrajectoryViewer needs significant refactoring for phase-based UI
- Consider adding pause/resume functionality for debugging
- Consider adding mode-specific logs/artifacts export

---

**Next Steps**: Review this plan, answer open questions, and begin Phase 1 implementation.
