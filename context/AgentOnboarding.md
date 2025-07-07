# YudaiV3 Agent Onboarding Guide

> **Last Updated:** 2025-01-07 • **Target:** AI Agents & New Developers  
> **Status:** Active Migration (TypeScript → FastAPI + SWE-agent integration)

## Directory Structure

```text
YudaiV3/
├── 📁 backend/                    # FastAPI backend (Python 3.11+)
│   ├── requirements.txt           # Python dependencies
│   ├── pyproject.toml             # Build configuration & metadata  
│   ├── types.py                   # Pydantic models & schemas
│   └── .venv/                     # Virtual environment
│
├── 📁 src/                        # React frontend (TypeScript)
│   ├── main.tsx                   # React app entry point
│   ├── App.tsx                    # Main app component & state management
│   ├── types.ts                   # TypeScript type definitions
│   ├── index.css                  # Global styles
│   └── 📁 components/             # React UI components
│       ├── Chat.tsx               # Chat interface with context integration
│       ├── TopBar.tsx             # Progress stepper & navigation
│       ├── Sidebar.tsx            # Tab navigation (chat, file-deps, context, ideas)
│       ├── ContextCards.tsx       # Context management & issue creation
│       ├── FileDependencies.tsx   # File tree & dependency viewer
│       ├── IdeasToImplement.tsx   # AI-generated implementation ideas
│       ├── DiffModal.tsx          # Pull request diff viewer
│       ├── DetailModal.tsx        # File detail viewer
│       └── Toast.tsx              # Notification system
│
├── 📁 Yudai-SWE-agent/           # SWE-agent submodule integration
│   ├── sweagent/                  # Core SWE-agent package
│   │   ├── run/                   # Entry points (run_single.py, run_batch.py)
│   │   ├── agent/                 # Agent behavior & main loop
│   │   └── environment/           # SWE-ReX environment interface
│   ├── tools/                     # Agent tool bundles
│   ├── config/                    # Agent & tool configurations
│   ├── pyproject.toml             # SWE-agent dependencies
│   └── docs/                      # SWE-agent documentation
│
├── 📁 context/                    # Project documentation
│   ├── PRD.md                     # Product Requirements Document (living)
│   └── AgentOnboarding.md         # This file
│
├── 📁 tests/                      # Test suites
├── package.json                   # Frontend dependencies & scripts
├── vite.config.ts                 # Vite build configuration
├── tailwind.config.js             # CSS framework configuration
└── README.md                      # Project overview
```

## Function Index

### Backend (Python/FastAPI)
| Function/Class | File | Purpose | Status |
|----------------|------|---------|---------|
| `ContextCardInput` | `backend/types.py` | Pydantic model for context card validation | ✅ Complete |
| `ChatRequest` | `backend/types.py` | Chat message request validation | ✅ Complete |
| `CLICommandInput` | `backend/types.py` | CLI execution request model | ✅ Complete |
| `CreateIssueRequest` | `backend/types.py` | GitHub issue creation request | ✅ Complete |
| `APIResponse` | `backend/types.py` | Standard API response wrapper | ✅ Complete |
| **FastAPI Server** | `backend/main.py` | **Missing:** Main API server & endpoints | ❌ **TODO** |
| **SWE-agent Integration** | `backend/swe_agent_integration/` | **Missing:** Agent orchestration layer | ❌ **TODO** |

### Frontend (React/TypeScript)
| Component/Function | File | Purpose | Key Features |
|-------------------|------|---------|--------------|
| `App()` | `src/App.tsx` | Main app state & routing | Tab management, progress tracking, modal state |
| `Chat()` | `src/components/Chat.tsx` | Chat interface | Message history, context integration (`/add` command) |
| `TopBar()` | `src/components/TopBar.tsx` | Progress indicator | Multi-step pipeline: PM → Architect → Test-Writer → Coder |
| `Sidebar()` | `src/components/Sidebar.tsx` | Navigation tabs | 4 tabs: chat, file-deps, context, ideas |
| `ContextCards()` | `src/components/ContextCards.tsx` | Context management | Add/remove context, issue creation trigger |
| `FileDependencies()` | `src/components/FileDependencies.tsx` | File tree browser | Expandable tree, token counting, internal/external classification |
| `IdeasToImplement()` | `src/components/IdeasToImplement.tsx` | AI idea generation | Complexity estimation (S/M/L/XL), confidence scoring |
| `DiffModal()` | `src/components/DiffModal.tsx` | PR diff viewer | Code diff display, branch information |

### SWE-agent Integration
| Function/Class | File | Purpose | Integration Point |
|----------------|------|---------|------------------|
| `main()` | `Yudai-SWE-agent/sweagent/run/run.py` | CLI entry point | Command routing & subcommand dispatch |
| `RunSingle.run()` | `Yudai-SWE-agent/sweagent/run/run_single.py` | Single issue execution | Main agent loop for individual GitHub issues |
| `DefaultAgent.run()` | `Yudai-SWE-agent/sweagent/agent/agents.py` | Agent main loop | Problem statement → environment setup → step execution |
| `SWEEnv()` | `Yudai-SWE-agent/sweagent/environment/swe_env.py` | Environment interface | Docker container management via SWE-ReX |

## Dependencies Diff

### 🔧 **Current State vs. Target State**

#### Backend Dependencies
```diff
# CURRENT (backend/requirements.txt)
+ fastapi==0.104.1
+ uvicorn[standard]==0.24.0  
+ pydantic==2.5.0
+ python-multipart==0.0.6

# MISSING (from PRD.md expectations)
- python-dotenv==1.0.1        # ❌ Environment variable management
- pydantic-settings==2.0.1    # ❌ Settings management  
- sweagent>=1.1.0             # ❌ SWE-agent integration package
- simple-json-logger==0.4.1   # ❌ DEPENDENCY ISSUE: Package not found in PyPI
```

#### Frontend Dependencies
```diff
# CURRENT (package.json)
+ react: ^18.3.1
+ react-dom: ^18.3.1
+ lucide-react: ^0.344.0      # Icon library
+ tailwindcss: ^3.4.1        # CSS framework
+ vite: ^5.4.2                # Build tool
+ typescript: ^5.5.3

# EXPRESS BACKEND (legacy/conflicting)
+ express: ^5.1.0             # ⚠️  Legacy TypeScript backend
+ @types/express: ^5.0.3      # ⚠️  Should be removed post-migration
```

#### SWE-agent Dependencies  
```diff
# FROM Yudai-SWE-agent/pyproject.toml
+ swe-rex>=1.2.0              # Container orchestration
+ rich                        # Terminal UI
+ ruamel.yaml                 # YAML parsing
+ tenacity                    # Retry mechanisms
+ litellm                     # Multi-LLM support
+ GitPython                   # Git operations
+ ghapi                       # GitHub API
+ flask                       # Web server (inspector)
+ textual>=1.0.0             # TUI framework
```

### 🚨 **Critical Dependency Issues**

1. **`simple-json-logger==0.4.1`** - **Package does not exist on PyPI**
   - Referenced in `context/PRD.md` line 123
   - Likely should be `python-json-logger` instead
   - **Action Required:** Update PRD.md and backend dependencies

2. **Backend Incomplete** - **No FastAPI server exists yet**
   - `backend/main.py` missing
   - No API endpoints implemented
   - **Action Required:** Complete TypeScript → FastAPI migration

3. **Duplicate Pydantic Settings** - **Version conflict in pyproject.toml**
   - `pydantic-settings==2.0.1` appears twice in backend/pyproject.toml
   - **Action Required:** Clean up duplicate entries

### 📋 **Next Steps for Agents**

#### High Priority
- [ ] **DEP-01:** Replace `simple-json-logger==0.4.1` with `python-json-logger` 
- [ ] **DEP-02:** Create `backend/main.py` FastAPI server with endpoints from `types.py`
- [ ] **DEP-03:** Add missing backend dependencies (`python-dotenv`, `pydantic-settings`)
- [ ] **DEP-04:** Implement SWE-agent integration layer

#### Medium Priority  
- [ ] **DEP-05:** Remove Express.js dependencies post-migration
- [ ] **DEP-06:** Add missing backend subdirectories (`utils/`, `swe_agent_integration/`)
- [ ] **DEP-07:** Create `backend/tests/` with pytest configuration

---

**🤖 Agent-Readable Metadata:**
```yaml
project_type: "react_fastapi_swe_agent"
migration_status: "typescript_to_python_in_progress"
critical_blockers: ["missing_fastapi_server", "invalid_dependency_simple_json_logger"]
agent_entry_points: ["sweagent run", "backend/main.py (when created)"]
deployment_target: "docker_swe_rex_containers"
```
