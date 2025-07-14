# Yudai V3 – Product Requirements Document (Living)

**Revision Date:** 2025‑01‑07 • **Revision ID:** PRD‑0.5
**Maintainers:** Pranay Kundu (PM/Tech Lead) | Core Platform Team

> **Living‑Doc Notice**
> This PRD is **source‑of‑truth** for Yudai V3. Every merge to `main` must bump the **Revision ID** and include an `## Changelog` entry summarising the delta. Down‑stream LLM agents parse the docstrings below—**do not delete them.**

```python
""" @prd-meta
revision_id = "PRD‑0.5"
updated = "2025‑01‑07T19:00:00+05:30"
status = "active"
"""
```

---

## 0. Changelog (aggregate)

| Rev | Date  | Author | Highlight                                                                                                                |
| --- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| 0.5 | 01‑07 | Pranay | **REALITY CHECK:** Updated directory structure & dependencies to match actual codebase; removed non-existent components |
| 0.4 | 07‑07 | Pranay | **MIGRATION:** Incomplete TypeScript → FastAPI backend transformation;      |
| 0.3 | 07‑07 | Pranay | Added directory‑structure section, function‑index, dependencies diff; created **AgentOnboarding.md**; checked off DOC‑01 |
| 0.2 | 07‑07 | Pranay | Marked PRD as living; added open‑TODO checklist & docstring schema                                                       |
| 0.1 | 07‑07 | Pranay | Initial SWE‑agent migration draft                                                                                        |

---

## 1. Background & Context

*Yudai V3 migrates its backend from Node TS → Python and embeds ****SWE‑agent**** for AI‑powered code generation. This PRD encodes project state for human & machine readers.*

---

## 2. Objectives & Key Results (OKRs)

(unchanged)

---

## 3. Scope

(unchanged)

---

## 4. Personas & Needs

(unchanged)

---

## 5. User Stories

(unchanged)

---

## 6. Functional Requirements

(unchanged)

---

## 7. Non‑Functional Requirements

(unchanged)

---

## 8. Architecture Overview

(unchanged)

---

## 9. Directory Structure (snapshot @PRD‑0.5)

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
│   └── AgentOnboarding.md         # Agent onboarding guide
│
├── 📁 tests/                      # Test suites
├── package.json                   # Frontend dependencies & scripts
├── vite.config.ts                 # Vite build configuration
├── tailwind.config.js             # CSS framework configuration
└── README.md                      # Project overview
```

---

## 10. Function Index (key public entry points)

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
| `DetailModal()` | `src/components/DetailModal.tsx` | File detail viewer | File content display, metadata |
| `Toast()` | `src/components/Toast.tsx` | Notification system | Success/error notifications |

---

## 11. Dependencies

### Backend Dependencies (Python/FastAPI)
```txt
# FastAPI Backend (migrated from TypeScript)
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
python-dotenv==1.0.1
pydantic-settings==2.0.1
pydantic-core==2.12.0
```

### Frontend Dependencies (React/TypeScript)
```json
{
  "dependencies": {
    "express": "^5.1.0",
    "lucide-react": "^0.344.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "zod": "^3.25.69"
  },
  "devDependencies": {
    "@types/express": "^5.0.3",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.5.3",
    "vite": "^5.4.2"
  }
}
```

### SWE-agent Dependencies
```txt
# FROM Yudai-SWE-agent/pyproject.toml
swe-rex>=1.2.0              # Container orchestration
rich                        # Terminal UI
ruamel.yaml                 # YAML parsing
tenacity                    # Retry mechanisms
litellm                     # Multi-LLM support
GitPython                   # Git operations
ghapi                       # GitHub API
flask                       # Web server (inspector)
textual>=1.0.0             # TUI framework
```

---

## 12. Milestones & Timeline

(unchanged)

---

## 13. Acceptance Criteria

(unchanged)

---

## 14. Success Metrics

(unchanged)

---

## 15. Risks & Mitigations

(unchanged)

---

## 16. Open TODOs

*(checked items are auto‑archived by CI)*

- [ ] **DEP-01:** Create `backend/main.py` FastAPI server with endpoints from `types.py`
- [ ] **DEP-02:** Implement SWE-agent integration layer
- [ ] **DEP-03:** Add missing backend subdirectories (`utils/`, `swe_agent_integration/`)
- [ ] **DEP-04:** Create `backend/tests/` with pytest configuration
- [ ] **DEP-05:** Remove Express.js dependencies post-migration
- [ ] **DEP-06:** Fix duplicate `pydantic-settings==2.0.1` in pyproject.toml

---

## 17. Versioning & Commit Guidelines

(unchanged)

---

*End of Living PRD – auto‑consumed by CI/LLM agents.*
