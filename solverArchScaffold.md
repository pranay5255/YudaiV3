# Solver Architecture Scaffold - Consolidated 2-File Implementation

> Consolidated implementation path for adding the parallel solver service backed by e2b sandboxes and the mini-swe-agent. All logic consolidated into 2 files with maximum code reuse from existing functions.

## Implementation Overview
**ONLY 2 FILES TO CREATE:**
1. `backend/solver/ai_solver.py` - Core solver logic with e2b integration
2. `backend/solver/solver_templates.py` - Template management and sandbox orchestration

**REUSE EXISTING CODE:**
- Session management from `session_routes.py` (already has solver endpoints)
- Database models from `models.py` (AISolveSession, AIModel, SWEAgentConfig already exist)
- GitHub operations from `githubOps.py`
- Chat integration from `ChatOps.py`
- Repository processing from `services/` (RepositorySnapshotService, FactsAndMemoriesService)

## 0. Prerequisites & Baseline Validation (Day 0)
- [x] FastAPI backend (`backend/run_server.py`) can reach Redis/Postgres
- [x] Session routes already have solver endpoints in `session_routes.py`
- [x] Database models already exist (AISolveSession, AIModel, SWEAgentConfig)
- [x] GitHub credentials handled in `backend/github`
- [x] Add missing dependencies to `backend/requirements.txt`
- [x] Minimal solver implementation created for demo purposes

## 1. Dependency Updates (Day 1 Morning)
**File: `backend/requirements.txt`**
- Add `e2b==0.8.0` (official SDK)
- Add `mini-swe-agent==0.1.0` (or current version)
- Add `redis==5.0.1` (for job queue)
- Add `rq==1.15.1` (Redis Queue worker)
- Add `tenacity==8.2.3` (retry logic)

## 2. Core Solver Implementation (Day 1 Afternoon)
**File: `backend/solver/ai_solver.py`**
```python
# Consolidated AI Solver with e2b integration
class AISolverAdapter:
    def __init__(self, db: Session):
        self.db = db
        self.e2b_client = E2BClient(api_key=settings.E2B_API_KEY)
    
    async def run_solver(self, issue_id, user_id, repo_url, branch, issue_content, issue_title, ai_model_id, swe_config_id):
        # Reuse existing session validation from session_routes.py
        # Create AISolveSession record (model already exists)
        # Launch e2b sandbox with template
        # Run mini-swe-agent
        # Stream results back to chat via ChatOps
        # Update session status
    
    async def cancel_session(self, solve_session_id, user_id):
        # Cancel running solver session
    
    def get_session_status(self, solve_session_id):
        # Get solver session statistics
```

**Key Functions to Implement:**
- `_launch_sandbox()` - e2b sandbox creation with template
- `_prepare_repository()` - Clone repo into sandbox (reuse GitHubOps)
- `_run_agent()` - Execute mini-swe-agent in sandbox
- `_collect_artifacts()` - Fetch results from sandbox
- `_cleanup_sandbox()` - Clean up resources

## 3. Template Management (Day 2 Morning)
**File: `backend/solver/solver_templates.py`**
```python
# Template management and sandbox orchestration
class SolverTemplateManager:
    def __init__(self):
        self.template_id = settings.E2B_TEMPLATE_ID
    
    def create_sandbox_template(self):
        # Create e2b template with Python environment
        # Add mini-swe-agent installation
        # Add repository cloning scripts
        # Add result collection scripts
    
    def prepare_sandbox_environment(self, sandbox, repo_url, branch, issue_data):
        # Clone repository using GitHubOps
        # Install dependencies
        # Set up issue context
        # Prepare mini-swe-agent configuration
```

**Template Scripts to Generate:**
- `prepare_repo.sh` - Clone repository (reuse GitHubOps logic)
- `install_deps.sh` - Install project dependencies
- `run_solver.py` - Execute mini-swe-agent (reuse existing agent logic)
- `collect_results.py` - Package results for retrieval

## 4. Integration with Existing Services (Day 2 Afternoon)
**Reuse Existing Code:**
- **Session Management**: Use existing `SessionService` from `session_service.py`
- **GitHub Operations**: Use existing `GitHubOps` from `githubOps.py`
- **Chat Integration**: Use existing `ChatOps` from `ChatOps.py`
- **Repository Processing**: Use existing `RepositorySnapshotService` from `services/`
- **Facts & Memories**: Use existing `FactsAndMemoriesService` from `services/`

**Modify Existing Files:**
- **`session_routes.py`**: Fix missing `await solver.run_solver()` call (line 1588)
- **`ChatOps.py`**: Add `append_solver_status()` method for real-time updates
- **`IssueOps.py`**: Add solver result integration after completion

## 5. Queue & Background Processing (Day 3 Morning)
**Reuse Existing Background Task Pattern:**
- Use existing `BackgroundTasks` from FastAPI (already in session_routes.py)
- Use existing `_index_repository_for_session_background()` pattern
- Implement `_run_solver_background()` following same pattern

**Redis Queue Integration:**
- Use existing Redis connection from database config
- Implement `enqueue_solver_job()` and `process_solver_job()`
- Reuse existing error handling and logging patterns

## 6. Real-time Updates & Chat Integration (Day 3 Afternoon)
**Reuse Existing Chat System:**
- Use existing `ChatOps.process_chat_message()` for status updates
- Use existing `ChatMessage` model for solver status messages
- Use existing WebSocket patterns from chat endpoints

**Status Update Flow:**
1. Solver starts → Post "Solver started" message via ChatOps
2. Sandbox created → Post "Environment prepared" message
3. Agent running → Post "Analyzing issue" message
4. Results ready → Post "Solution generated" message with results

## 7. Error Handling & Observability (Day 4)
**Reuse Existing Error Patterns:**
- Use existing `create_standardized_error()` from session_routes.py
- Use existing logging patterns from `utils.py`
- Use existing database transaction patterns

**Health Checks:**
- Reuse existing health check pattern from session_routes.py
- Add e2b connectivity check
- Add mini-swe-agent availability check

## 8. Testing Strategy (Day 5)
**Reuse Existing Test Patterns:**
- Use existing test database setup
- Mock e2b client (similar to existing GitHub API mocks)
- Use existing session test patterns from session_routes.py

## 9. Deployment & Configuration (Day 6)
**Reuse Existing Config:**
- Use existing environment variable patterns
- Use existing Docker configuration
- Use existing database migration patterns

**New Environment Variables:**
- `E2B_API_KEY` - e2b API key
- `E2B_TEMPLATE_ID` - e2b template ID
- `REDIS_URL` - Redis connection for job queue

## 10. Detailed Implementation Tasks

### File 1: `backend/solver/ai_solver.py` - Core Solver Logic

**Class Structure:**
```python
class AISolverAdapter:
    def __init__(self, db: Session)
    async def run_solver(self, issue_id, user_id, repo_url, branch, issue_content, issue_title, ai_model_id, swe_config_id)
    async def cancel_session(self, solve_session_id, user_id)
    def get_session_status(self, solve_session_id)
    async def _launch_sandbox(self, template_id, metadata)
    async def _prepare_repository(self, sandbox, repo_url, branch, user_id)
    async def _run_agent(self, sandbox, issue_data, ai_model_id, swe_config_id)
    async def _stream_results(self, sandbox, session_id, user_id)
    async def _collect_artifacts(self, sandbox, solve_session_id)
    async def _cleanup_sandbox(self, sandbox_id)
    def _update_session_status(self, solve_session_id, status, error_message=None)
    async def _post_status_to_chat(self, session_id, user_id, message, status_type)
```

**Step-by-Step Implementation:**

**Step 1: Basic Class Setup**
- [ ] Import required dependencies (e2b, redis, existing models)
- [ ] Initialize E2B client with API key from settings
- [ ] Add database session handling
- [ ] Add error handling and logging setup

**Step 2: run_solver() Method**
- [ ] Validate session exists and belongs to user (reuse from session_routes.py)
- [ ] Create AISolveSession record in database
- [ ] Launch e2b sandbox with template
- [ ] Prepare repository in sandbox (clone, install deps)
- [ ] Run mini-swe-agent with issue data
- [ ] Stream results back to chat
- [ ] Collect artifacts and update database
- [ ] Clean up sandbox resources
- [ ] Update session status to completed/failed

**Step 3: cancel_session() Method**
- [ ] Validate solve session exists and belongs to user
- [ ] Update session status to cancelled
- [ ] Terminate e2b sandbox if running
- [ ] Post cancellation message to chat
- [ ] Clean up resources

**Step 4: get_session_status() Method**
- [ ] Query AISolveSession from database
- [ ] Return comprehensive status including:
  - Current status (pending/running/completed/failed/cancelled)
  - Progress percentage
  - Error messages if any
  - Artifact URLs if completed
  - Execution time statistics

**Step 5: Helper Methods**
- [ ] `_launch_sandbox()` - Create e2b sandbox with metadata
- [ ] `_prepare_repository()` - Clone repo, install dependencies
- [ ] `_run_agent()` - Execute mini-swe-agent with proper configuration
- [ ] `_stream_results()` - Stream logs to chat via ChatOps
- [ ] `_collect_artifacts()` - Fetch results from sandbox
- [ ] `_cleanup_sandbox()` - Clean up e2b resources
- [ ] `_update_session_status()` - Update database record
- [ ] `_post_status_to_chat()` - Post status updates to chat

### File 2: `backend/solver/solver_templates.py` - Template Management

**Class Structure:**
```python
class SolverTemplateManager:
    def __init__(self)
    async def create_sandbox_template(self)
    async def prepare_sandbox_environment(self, sandbox, repo_url, branch, issue_data, user_id)
    def _generate_prepare_repo_script(self, repo_url, branch, github_token)
    def _generate_install_deps_script(self, project_type)
    def _generate_run_solver_script(self, issue_data, ai_model_id, swe_config_id)
    def _generate_collect_results_script(self)
    async def _clone_repository(self, sandbox, repo_url, branch, github_token)
    async def _install_dependencies(self, sandbox, project_type)
    async def _setup_issue_context(self, sandbox, issue_data)
    async def _configure_agent(self, sandbox, ai_model_id, swe_config_id)
```

**Step-by-Step Implementation:**

**Step 1: Template Creation**
- [ ] Create e2b template with Python environment
- [ ] Install mini-swe-agent and dependencies
- [ ] Add repository cloning scripts
- [ ] Add dependency installation scripts
- [ ] Add result collection scripts
- [ ] Configure environment variables

**Step 2: Sandbox Environment Preparation**
- [ ] Clone repository using GitHub token (reuse GitHubOps logic)
- [ ] Install project dependencies (detect type: Python/Node.js/etc.)
- [ ] Set up issue context files
- [ ] Configure mini-swe-agent with proper settings
- [ ] Prepare execution environment

**Step 3: Script Generation**
- [ ] `_generate_prepare_repo_script()` - Clone repo with proper authentication
- [ ] `_generate_install_deps_script()` - Install dependencies based on project type
- [ ] `_generate_run_solver_script()` - Execute mini-swe-agent with issue data
- [ ] `_generate_collect_results_script()` - Package results for retrieval

**Step 4: Repository Operations**
- [ ] `_clone_repository()` - Use GitHubOps for repository access
- [ ] `_install_dependencies()` - Detect and install project dependencies
- [ ] `_setup_issue_context()` - Create issue context files
- [ ] `_configure_agent()` - Set up mini-swe-agent configuration

### Integration Tasks

**Fix session_routes.py (Line 1588):**
- [ ] Fix missing `await solver.run_solver()` call
- [ ] Add proper error handling for solver failures
- [ ] Add background task integration

**Add ChatOps Integration:**
- [ ] Add `append_solver_status()` method to ChatOps
- [ ] Add real-time status updates during solver execution
- [ ] Add result posting when solver completes

**Add IssueOps Integration:**
- [ ] Add solver result integration after completion
- [ ] Add diff summary attachment to issues
- [ ] Add commit suggestion generation

**Add Redis Queue Processing:**
- [ ] Implement `enqueue_solver_job()` function
- [ ] Implement `process_solver_job()` worker
- [ ] Add job status tracking
- [ ] Add retry logic for failed jobs

**Add Health Checks:**
- [ ] Add e2b connectivity check
- [ ] Add mini-swe-agent availability check
- [ ] Add Redis queue health check
- [ ] Add database connectivity check

## Key Implementation Details

### Code Reuse Strategy:
1. **Database Models**: Use existing AISolveSession, AIModel, SWEAgentConfig
2. **Session Management**: Reuse SessionService patterns
3. **GitHub Operations**: Reuse GitHubOps for repository access
4. **Chat Integration**: Reuse ChatOps for real-time updates
5. **Background Tasks**: Reuse existing BackgroundTasks pattern
6. **Error Handling**: Reuse existing error response patterns
7. **Logging**: Reuse existing logging configuration

### File Structure:
```
backend/
├── solver/
│   ├── __init__.py
│   ├── ai_solver.py          # Core solver logic (NEW)
│   └── solver_templates.py   # Template management (NEW)
├── daifuUserAgent/
│   ├── session_routes.py      # Already has solver endpoints
│   ├── ChatOps.py            # Add solver status methods
│   └── IssueOps.py            # Add solver result integration
└── models.py                  # Already has solver models
```

### API Endpoints (Already Implemented):
- `POST /sessions/{session_id}/solve/start`
- `GET /sessions/{session_id}/solve/sessions/{solve_session_id}`
- `GET /sessions/{session_id}/solve/sessions/{solve_session_id}/stats`
- `POST /sessions/{session_id}/solve/sessions/{solve_session_id}/cancel`
- `GET /sessions/{session_id}/solve/sessions`
- `GET /sessions/{session_id}/solve/health`

> This consolidated approach maximizes code reuse while implementing the full solver functionality in just 2 new files.

---

## 11. Memory Management System - Conversational Memory Curation

### Overview
An intelligent memory system that allows the agent to propose memories during conversations, which users can approve, edit, or discard. Integrates with existing `FactsAndMemoriesService` to provide long-term context for the agent.

### User Flow
```
Conversation
   ↓
Agent proposes memory (draft)
   ↓
Memory appears in Turn Summary ("1 Pending Memory")
   ↓
User clicks → review screen opens inside Chat
   ↓
User options:
   - Approve (add to workspace long-term memory)
   - Edit (curate before saving)
   - Discard (reject entirely)
   ↓
Agent loop continues with curated memory context
```

### File Structure
**ONLY 1 FILE TO CREATE:**
1. `backend/daifuUserAgent/services/memory_manager.py` - Complete memory lifecycle management

**REUSE EXISTING CODE:**
- `FactsAndMemoriesService` from `services/facts_and_memories.py`
- Session management from `session_routes.py`
- Chat integration from `ChatOps.py`
- Database models from `models.py` (add new MemoryEntry model)

### Database Schema Addition

**Add to `backend/models.py`:**
```python
class MemoryEntry(Base):
    """User-curated memories from conversations and repository analysis."""
    
    __tablename__ = "memory_entries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Memory content
    memory_type = Column(String, nullable=False)  # 'fact', 'goal', 'preference', 'context'
    memory_content = Column(Text, nullable=False)
    memory_category = Column(String, nullable=True)  # 'repository', 'workflow', 'coding_style', etc.
    
    # Lifecycle state
    state = Column(String, nullable=False, default="pending")  # pending, approved, edited, discarded
    proposed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Source tracking
    source_message_id = Column(String, nullable=True)  # Chat message that triggered proposal
    source_context = Column(JSON, nullable=True)  # Snapshot of conversation context
    
    # User edits
    original_content = Column(Text, nullable=True)  # Original proposed content before edits
    edit_count = Column(Integer, default=0)
    
    # Metadata
    relevance_score = Column(Float, nullable=True)  # AI-assigned importance score
    tags = Column(JSON, default=list)  # ['python', 'fastapi', 'authentication']
    related_files = Column(JSON, default=list)  # Files mentioned in memory
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="memories")


# Add to ChatSession model:
class ChatSession(Base):
    # ... existing fields ...
    memories = relationship("MemoryEntry", back_populates="session", cascade="all, delete-orphan")
```

### Core Implementation

**File: `backend/daifuUserAgent/services/memory_manager.py`**

```python
"""Memory management system for conversational memory curation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from ...models import ChatMessage, ChatSession, MemoryEntry
from .facts_and_memories import FactsAndMemoriesResult, FactsAndMemoriesService, RepositorySnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Memory State Management
# ---------------------------------------------------------------------------


class MemoryState(str, Enum):
    """Memory lifecycle states."""
    
    PENDING = "pending"      # Awaiting user review
    APPROVED = "approved"    # User approved without edits
    EDITED = "edited"        # User edited before approving
    DISCARDED = "discarded"  # User rejected


class MemoryType(str, Enum):
    """Types of memories the agent can propose."""
    
    FACT = "fact"                # Repository facts (from FactsAndMemoriesService)
    GOAL = "goal"                # User goals or objectives
    PREFERENCE = "preference"    # User preferences (coding style, patterns)
    CONTEXT = "context"          # Session context or workflow patterns


class MemoryCategory(str, Enum):
    """Memory categorization for organization."""
    
    REPOSITORY = "repository"
    WORKFLOW = "workflow"
    CODING_STYLE = "coding_style"
    ARCHITECTURE = "architecture"
    BUSINESS_LOGIC = "business_logic"
    PREFERENCES = "preferences"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class MemoryProposal:
    """Agent's proposed memory draft."""
    
    memory_type: str
    memory_content: str
    memory_category: Optional[str] = None
    source_message_id: Optional[str] = None
    relevance_score: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    source_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "memory_type": self.memory_type,
            "memory_content": self.memory_content,
            "memory_category": self.memory_category,
            "source_message_id": self.source_message_id,
            "relevance_score": self.relevance_score,
            "tags": self.tags,
            "related_files": self.related_files,
            "source_context": self.source_context,
        }


@dataclass
class MemoryReview:
    """User's review action on a memory."""
    
    memory_id: str
    action: str  # 'approve', 'edit', 'discard'
    edited_content: Optional[str] = None
    edited_category: Optional[str] = None
    edited_tags: Optional[List[str]] = None


@dataclass
class MemorySummary:
    """Summary of memory state for turn summary display."""
    
    pending_count: int
    total_approved: int
    recent_proposals: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "pending_count": self.pending_count,
            "total_approved": self.total_approved,
            "recent_proposals": self.recent_proposals,
        }


# ---------------------------------------------------------------------------
# Memory Manager - Core Service
# ---------------------------------------------------------------------------


class MemoryManager:
    """
    Orchestrates the complete memory lifecycle:
    - Proposing memories from conversations
    - Managing user review (approve/edit/discard)
    - Providing memory context to the agent
    - Integrating with FactsAndMemoriesService
    """
    
    def __init__(self, db: Session) -> None:
        self.db = db
        self.facts_service = FactsAndMemoriesService()
    
    # -----------------------------------------------------------------------
    # Memory Proposal (Agent-initiated)
    # -----------------------------------------------------------------------
    
    async def propose_memory(
        self,
        session_id: str,
        user_id: str,
        proposal: MemoryProposal,
    ) -> MemoryEntry:
        """
        Agent proposes a new memory during conversation.
        Creates a pending memory entry for user review.
        """
        memory = MemoryEntry(
            session_id=session_id,
            user_id=user_id,
            memory_type=proposal.memory_type,
            memory_content=proposal.memory_content,
            memory_category=proposal.memory_category,
            state=MemoryState.PENDING,
            source_message_id=proposal.source_message_id,
            source_context=proposal.source_context,
            relevance_score=proposal.relevance_score,
            tags=proposal.tags,
            related_files=proposal.related_files,
            proposed_at=datetime.utcnow(),
        )
        
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        
        logger.info(
            f"Memory proposed for session {session_id}: "
            f"type={proposal.memory_type}, id={memory.id}"
        )
        
        return memory
    
    async def propose_from_facts_and_memories(
        self,
        session_id: str,
        user_id: str,
        snapshot: RepositorySnapshot,
        conversation: Optional[Sequence[Dict[str, Any]]] = None,
        max_messages: int = 10,
    ) -> List[MemoryEntry]:
        """
        Generate memory proposals from repository analysis using FactsAndMemoriesService.
        Automatically converts facts and memories into memory proposals.
        """
        # Generate facts & memories using existing service
        result: FactsAndMemoriesResult = await self.facts_service.generate(
            snapshot=snapshot,
            conversation=conversation,
            max_messages=max_messages,
        )
        
        proposed_memories: List[MemoryEntry] = []
        
        # Convert facts to memory proposals
        for fact in result.facts:
            proposal = MemoryProposal(
                memory_type=MemoryType.FACT,
                memory_content=fact,
                memory_category=MemoryCategory.REPOSITORY,
                relevance_score=0.8,
                tags=self._extract_tags(fact),
                related_files=self._extract_file_paths(fact),
                source_context={
                    "source": "facts_and_memories_service",
                    "raw_response": result.raw_response,
                },
            )
            memory = await self.propose_memory(session_id, user_id, proposal)
            proposed_memories.append(memory)
        
        # Convert memories to context proposals
        for memory_text in result.memories:
            proposal = MemoryProposal(
                memory_type=MemoryType.CONTEXT,
                memory_content=memory_text,
                memory_category=MemoryCategory.WORKFLOW,
                relevance_score=0.7,
                tags=self._extract_tags(memory_text),
                source_context={
                    "source": "facts_and_memories_service",
                    "raw_response": result.raw_response,
                },
            )
            memory = await self.propose_memory(session_id, user_id, proposal)
            proposed_memories.append(memory)
        
        # Convert highlights to context proposals
        for highlight in result.highlights:
            proposal = MemoryProposal(
                memory_type=MemoryType.CONTEXT,
                memory_content=highlight,
                memory_category=MemoryCategory.OTHER,
                relevance_score=0.6,
                tags=self._extract_tags(highlight),
                related_files=self._extract_file_paths(highlight),
                source_context={
                    "source": "facts_and_memories_service",
                    "raw_response": result.raw_response,
                },
            )
            memory = await self.propose_memory(session_id, user_id, proposal)
            proposed_memories.append(memory)
        
        logger.info(
            f"Proposed {len(proposed_memories)} memories from Facts & Memories "
            f"service for session {session_id}"
        )
        
        return proposed_memories
    
    # -----------------------------------------------------------------------
    # Memory Review (User-initiated)
    # -----------------------------------------------------------------------
    
    def review_memory(
        self,
        memory_id: str,
        user_id: str,
        review: MemoryReview,
    ) -> MemoryEntry:
        """
        Process user review of a proposed memory.
        Handles approve, edit, and discard actions.
        """
        memory = self.db.query(MemoryEntry).filter(
            and_(
                MemoryEntry.id == memory_id,
                MemoryEntry.user_id == user_id,
            )
        ).first()
        
        if not memory:
            raise ValueError(f"Memory {memory_id} not found for user {user_id}")
        
        if memory.state != MemoryState.PENDING:
            raise ValueError(f"Memory {memory_id} is not pending review (state: {memory.state})")
        
        memory.reviewed_at = datetime.utcnow()
        
        if review.action == "approve":
            memory.state = MemoryState.APPROVED
            logger.info(f"Memory {memory_id} approved by user {user_id}")
        
        elif review.action == "edit":
            if not review.edited_content:
                raise ValueError("Edited content required for edit action")
            
            # Store original content
            memory.original_content = memory.memory_content
            memory.memory_content = review.edited_content
            memory.edit_count += 1
            memory.state = MemoryState.EDITED
            
            # Update metadata if provided
            if review.edited_category:
                memory.memory_category = review.edited_category
            if review.edited_tags:
                memory.tags = review.edited_tags
            
            logger.info(f"Memory {memory_id} edited by user {user_id} (edit #{memory.edit_count})")
        
        elif review.action == "discard":
            memory.state = MemoryState.DISCARDED
            logger.info(f"Memory {memory_id} discarded by user {user_id}")
        
        else:
            raise ValueError(f"Invalid review action: {review.action}")
        
        self.db.commit()
        self.db.refresh(memory)
        
        return memory
    
    # -----------------------------------------------------------------------
    # Memory Retrieval & Context
    # -----------------------------------------------------------------------
    
    def get_pending_memories(
        self,
        session_id: str,
        user_id: str,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """Get all pending memories for user review."""
        return (
            self.db.query(MemoryEntry)
            .filter(
                and_(
                    MemoryEntry.session_id == session_id,
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.state == MemoryState.PENDING,
                )
            )
            .order_by(desc(MemoryEntry.proposed_at))
            .limit(limit)
            .all()
        )
    
    def get_approved_memories(
        self,
        session_id: str,
        user_id: str,
        limit: Optional[int] = 100,
    ) -> List[MemoryEntry]:
        """
        Get approved memories for agent context.
        Includes both approved and edited (which are approved after editing).
        """
        return (
            self.db.query(MemoryEntry)
            .filter(
                and_(
                    MemoryEntry.session_id == session_id,
                    MemoryEntry.user_id == user_id,
                    or_(
                        MemoryEntry.state == MemoryState.APPROVED,
                        MemoryEntry.state == MemoryState.EDITED,
                    ),
                )
            )
            .order_by(desc(MemoryEntry.relevance_score), desc(MemoryEntry.reviewed_at))
            .limit(limit)
            .all()
        )
    
    def get_memory_summary(
        self,
        session_id: str,
        user_id: str,
    ) -> MemorySummary:
        """
        Get memory summary for turn summary display.
        Shows pending count and recent proposals.
        """
        pending_memories = self.get_pending_memories(session_id, user_id, limit=10)
        
        approved_count = (
            self.db.query(MemoryEntry)
            .filter(
                and_(
                    MemoryEntry.session_id == session_id,
                    MemoryEntry.user_id == user_id,
                    or_(
                        MemoryEntry.state == MemoryState.APPROVED,
                        MemoryEntry.state == MemoryState.EDITED,
                    ),
                )
            )
            .count()
        )
        
        recent_proposals = [
            {
                "id": mem.id,
                "type": mem.memory_type,
                "content": mem.memory_content[:200] + "..." if len(mem.memory_content) > 200 else mem.memory_content,
                "category": mem.memory_category,
                "proposed_at": mem.proposed_at.isoformat(),
                "relevance_score": mem.relevance_score,
            }
            for mem in pending_memories
        ]
        
        return MemorySummary(
            pending_count=len(pending_memories),
            total_approved=approved_count,
            recent_proposals=recent_proposals,
        )
    
    def build_memory_context(
        self,
        session_id: str,
        user_id: str,
        memory_types: Optional[List[str]] = None,
    ) -> str:
        """
        Build formatted memory context string for agent prompts.
        Retrieves approved memories and formats them for LLM context.
        """
        approved = self.get_approved_memories(session_id, user_id, limit=50)
        
        if memory_types:
            approved = [m for m in approved if m.memory_type in memory_types]
        
        if not approved:
            return "No curated memories available."
        
        # Group by type
        by_type: Dict[str, List[MemoryEntry]] = {}
        for mem in approved:
            by_type.setdefault(mem.memory_type, []).append(mem)
        
        sections = []
        
        if MemoryType.FACT in by_type:
            facts = by_type[MemoryType.FACT]
            sections.append("## Repository Facts")
            for mem in facts:
                sections.append(f"- {mem.memory_content}")
        
        if MemoryType.GOAL in by_type:
            goals = by_type[MemoryType.GOAL]
            sections.append("\n## User Goals")
            for mem in goals:
                sections.append(f"- {mem.memory_content}")
        
        if MemoryType.PREFERENCE in by_type:
            prefs = by_type[MemoryType.PREFERENCE]
            sections.append("\n## User Preferences")
            for mem in prefs:
                sections.append(f"- {mem.memory_content}")
        
        if MemoryType.CONTEXT in by_type:
            contexts = by_type[MemoryType.CONTEXT]
            sections.append("\n## Session Context")
            for mem in contexts:
                sections.append(f"- {mem.memory_content}")
        
        return "\n".join(sections)
    
    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------
    
    @staticmethod
    def _extract_tags(text: str) -> List[str]:
        """Extract potential tags from text (simple heuristic)."""
        tags = []
        common_tags = [
            "python", "fastapi", "typescript", "react", "database", "api",
            "authentication", "authorization", "testing", "deployment",
            "performance", "security", "frontend", "backend",
        ]
        
        text_lower = text.lower()
        for tag in common_tags:
            if tag in text_lower:
                tags.append(tag)
        
        return tags[:5]  # Limit to 5 tags
    
    @staticmethod
    def _extract_file_paths(text: str) -> List[str]:
        """Extract file paths from text (simple pattern matching)."""
        import re
        
        # Match common file path patterns
        patterns = [
            r'`([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)`',  # `path/to/file.py`
            r'[\s]([a-zA-Z0-9_./\\-]+/[a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)',  # path/to/file.py
        ]
        
        paths = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            paths.extend(matches)
        
        return list(set(paths))[:10]  # Deduplicate and limit to 10


# ---------------------------------------------------------------------------
# Pydantic Models for API
# ---------------------------------------------------------------------------


from pydantic import BaseModel, Field


class ProposeMemoryRequest(BaseModel):
    """Request to propose a new memory."""
    
    memory_type: str = Field(..., description="Type of memory: fact, goal, preference, context")
    memory_content: str = Field(..., description="Content of the memory")
    memory_category: Optional[str] = Field(None, description="Category: repository, workflow, etc.")
    source_message_id: Optional[str] = Field(None, description="Source chat message ID")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    related_files: List[str] = Field(default_factory=list)


class ReviewMemoryRequest(BaseModel):
    """Request to review a memory."""
    
    memory_id: str = Field(..., description="ID of memory to review")
    action: str = Field(..., description="Action: approve, edit, discard")
    edited_content: Optional[str] = Field(None, description="Edited content if action is edit")
    edited_category: Optional[str] = Field(None)
    edited_tags: Optional[List[str]] = Field(None)


class MemoryManagementRequest(BaseModel):
    """Unified request for memory management operations."""
    
    operation: str = Field(..., description="Operation: propose, review, get_pending, get_approved, get_summary, build_context")
    
    # For propose operation
    propose: Optional[ProposeMemoryRequest] = None
    
    # For review operation
    review: Optional[ReviewMemoryRequest] = None
    
    # For build_context operation
    memory_types: Optional[List[str]] = None


class MemoryManagementResponse(BaseModel):
    """Unified response for memory management operations."""
    
    success: bool
    operation: str
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
```

### Single API Endpoint Implementation

**Add to `backend/daifuUserAgent/session_routes.py`:**

```python
@router.post(
    "/sessions/{session_id}/memories/manage",
    summary="Unified memory management endpoint",
    description="Handles all memory operations: propose, review, retrieve, and context building",
)
async def manage_session_memories(
    session_id: str,
    request: MemoryManagementRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> MemoryManagementResponse:
    """
    Unified API for complete memory lifecycle management.
    
    Operations:
    - propose: Agent proposes a new memory
    - review: User reviews a pending memory (approve/edit/discard)
    - get_pending: Get all pending memories for review
    - get_approved: Get all approved memories for context
    - get_summary: Get memory summary for turn display
    - build_context: Build formatted memory context for agent prompts
    """
    user_id = current_user["id"]
    
    # Validate session ownership
    session = db.query(ChatSession).filter(
        and_(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
        )
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found or access denied",
        )
    
    # Initialize memory manager
    memory_manager = MemoryManager(db)
    
    try:
        # Route to appropriate operation
        if request.operation == "propose":
            if not request.propose:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'propose' data for propose operation",
                )
            
            proposal = MemoryProposal(
                memory_type=request.propose.memory_type,
                memory_content=request.propose.memory_content,
                memory_category=request.propose.memory_category,
                source_message_id=request.propose.source_message_id,
                relevance_score=request.propose.relevance_score,
                tags=request.propose.tags,
                related_files=request.propose.related_files,
            )
            
            memory = await memory_manager.propose_memory(session_id, user_id, proposal)
            
            return MemoryManagementResponse(
                success=True,
                operation="propose",
                data={
                    "memory_id": memory.id,
                    "state": memory.state,
                    "proposed_at": memory.proposed_at.isoformat(),
                },
                message="Memory proposed successfully",
            )
        
        elif request.operation == "review":
            if not request.review:
                raise HTTPException(
                    status_code=400,
                    detail="Missing 'review' data for review operation",
                )
            
            review = MemoryReview(
                memory_id=request.review.memory_id,
                action=request.review.action,
                edited_content=request.review.edited_content,
                edited_category=request.review.edited_category,
                edited_tags=request.review.edited_tags,
            )
            
            memory = memory_manager.review_memory(
                memory_id=review.memory_id,
                user_id=user_id,
                review=review,
            )
            
            return MemoryManagementResponse(
                success=True,
                operation="review",
                data={
                    "memory_id": memory.id,
                    "state": memory.state,
                    "reviewed_at": memory.reviewed_at.isoformat() if memory.reviewed_at else None,
                },
                message=f"Memory {review.action}ed successfully",
            )
        
        elif request.operation == "get_pending":
            pending = memory_manager.get_pending_memories(session_id, user_id)
            
            return MemoryManagementResponse(
                success=True,
                operation="get_pending",
                data={
                    "count": len(pending),
                    "memories": [
                        {
                            "id": mem.id,
                            "type": mem.memory_type,
                            "content": mem.memory_content,
                            "category": mem.memory_category,
                            "proposed_at": mem.proposed_at.isoformat(),
                            "relevance_score": mem.relevance_score,
                            "tags": mem.tags,
                            "related_files": mem.related_files,
                        }
                        for mem in pending
                    ],
                },
            )
        
        elif request.operation == "get_approved":
            approved = memory_manager.get_approved_memories(session_id, user_id)
            
            return MemoryManagementResponse(
                success=True,
                operation="get_approved",
                data={
                    "count": len(approved),
                    "memories": [
                        {
                            "id": mem.id,
                            "type": mem.memory_type,
                            "content": mem.memory_content,
                            "category": mem.memory_category,
                            "state": mem.state,
                            "reviewed_at": mem.reviewed_at.isoformat() if mem.reviewed_at else None,
                        }
                        for mem in approved
                    ],
                },
            )
        
        elif request.operation == "get_summary":
            summary = memory_manager.get_memory_summary(session_id, user_id)
            
            return MemoryManagementResponse(
                success=True,
                operation="get_summary",
                data=summary.to_dict(),
            )
        
        elif request.operation == "build_context":
            context = memory_manager.build_memory_context(
                session_id,
                user_id,
                memory_types=request.memory_types,
            )
            
            return MemoryManagementResponse(
                success=True,
                operation="build_context",
                data={"context": context},
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation: {request.operation}",
            )
    
    except ValueError as e:
        logger.warning(f"Memory management error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Memory management failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Memory management operation failed: {str(e)}",
        )
```

### Integration with Chat System

**Add to `backend/daifuUserAgent/ChatOps.py`:**

```python
async def propose_memory_from_conversation(
    self,
    session_id: str,
    user_id: str,
    conversation_messages: List[Dict[str, Any]],
) -> List[MemoryEntry]:
    """
    Analyze recent conversation and propose relevant memories.
    Called automatically during chat processing.
    """
    from .services.memory_manager import MemoryManager, MemoryProposal, MemoryType
    
    memory_manager = MemoryManager(self.db)
    
    # Extract key insights from conversation
    proposals = []
    
    for message in conversation_messages[-5:]:  # Last 5 messages
        content = message.get("content", "")
        
        # Simple heuristics for memory proposal
        if "prefer" in content.lower() or "like to" in content.lower():
            proposals.append(MemoryProposal(
                memory_type=MemoryType.PREFERENCE,
                memory_content=content,
                memory_category="preferences",
                source_message_id=message.get("id"),
                relevance_score=0.7,
            ))
        
        elif "goal" in content.lower() or "want to" in content.lower():
            proposals.append(MemoryProposal(
                memory_type=MemoryType.GOAL,
                memory_content=content,
                memory_category="workflow",
                source_message_id=message.get("id"),
                relevance_score=0.8,
            ))
    
    # Create memory proposals
    memories = []
    for proposal in proposals:
        memory = await memory_manager.propose_memory(session_id, user_id, proposal)
        memories.append(memory)
    
    return memories
```

### Frontend Integration Points

**Expected frontend implementation in `src/components/`:**

1. **Turn Summary Component** - Display pending memory count
   - Shows "1 Pending Memory" badge
   - Clickable to open memory review modal

2. **Memory Review Modal** - Review interface
   - Display pending memory content
   - Action buttons: Approve, Edit, Discard
   - Edit mode with textarea for content modification

3. **Memory Context Panel** - Display approved memories
   - Shows curated memories in sidebar
   - Organized by category
   - Searchable and filterable

### Usage Example

**Agent proposes memory during conversation:**
```python
# In ChatOps.process_chat_message()
memory_manager = MemoryManager(db)

# Propose fact from repository analysis
await memory_manager.propose_memory(
    session_id=session_id,
    user_id=user_id,
    proposal=MemoryProposal(
        memory_type="fact",
        memory_content="FastAPI backend uses Pydantic v2 for all validation",
        memory_category="repository",
        relevance_score=0.9,
        tags=["fastapi", "pydantic", "validation"],
        related_files=["backend/models.py", "backend/daifuUserAgent/session_routes.py"],
    ),
)
```

**User reviews memory:**
```bash
# Approve
POST /sessions/{session_id}/memories/manage
{
  "operation": "review",
  "review": {
    "memory_id": "mem_123",
    "action": "approve"
  }
}

# Edit before approving
POST /sessions/{session_id}/memories/manage
{
  "operation": "review",
  "review": {
    "memory_id": "mem_123",
    "action": "edit",
    "edited_content": "FastAPI backend uses Pydantic v2 for input validation and response schemas",
    "edited_tags": ["fastapi", "pydantic", "api-design"]
  }
}
```

**Get memory context for agent:**
```python
# In LLMService.generate_response()
memory_manager = MemoryManager(db)
memory_context = memory_manager.build_memory_context(session_id, user_id)

prompt = f"""
{memory_context}

## Current Request
{user_message}
"""
```

### Implementation Checklist

- [ ] Add `MemoryEntry` model to `backend/models.py`
- [ ] Create `backend/daifuUserAgent/services/memory_manager.py`
- [ ] Add memory management endpoint to `session_routes.py`
- [ ] Integrate with `ChatOps.py` for automatic proposals
- [ ] Add memory context to `LLMService.generate_response()`
- [ ] Update database migration for new table
- [ ] Add frontend components for memory review
- [ ] Add turn summary badge for pending memories
- [ ] Add tests for memory lifecycle
- [ ] Document memory management API

### Key Benefits

1. **Minimal Implementation**: One file + one API endpoint
2. **Reuses Existing Code**: Builds on FactsAndMemoriesService
3. **User Control**: Users curate what the agent remembers
4. **Better Context**: Agent gets high-quality, user-approved context
5. **Incremental Learning**: Memory improves over conversation sessions
6. **Privacy Friendly**: Users can discard sensitive information

This memory system provides a foundation for long-term agent memory that respects user preferences and improves over time.
