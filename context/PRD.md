# Yudai V3 – Product Requirements Document (Living)

**Revision Date:** 2025‑07‑07 • **Revision ID:** PRD‑0.4
**Maintainers:** Pranay Kundu (PM/Tech Lead) | Core Platform Team

> **Living‑Doc Notice**
> This PRD is **source‑of‑truth** for Yudai V3. Every merge to `main` must bump the **Revision ID** and include an `## Changelog` entry summarising the delta. Down‑stream LLM agents parse the docstrings below—**do not delete them.**

```python
""" @prd-meta
revision_id = "PRD‑0.4"
updated = "2025‑07‑07T19:00:00+05:30"
status = "active"
"""
```

---

## 0. Changelog (aggregate)

| Rev | Date  | Author | Highlight                                                                                                                |
| --- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| 0.4 | 07‑07 | Pranay | **MIGRATION:** Completed TypeScript → FastAPI backend transformation; updated deps, structure & function index         |
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

## 9. Directory Structure (snapshot @PRD‑0.4)

```text
backend/
├── main.py                  # FastAPI server
├── types.py                 # Pydantic models & schemas
├── requirements.txt         # Python deps lock‑file
├── pyproject.toml           # Build meta
├── utils/
│   └── run_yudai_cli.py     # CLI runner utility
├── swe_agent_integration/   # Tool wrappers & env
│   ├── tools.py
│   ├── commands.py
│   └── environment.py
├── run_swe_agent.py         # Entry‑point for agent
└── tests/                   # pytest suite
```

Front‑end lives in `src/`, legacy TS CLI in `YudaiCLI/` sub‑module.

---

## 10. Function Index (key public entry points)

| Name                                         | File                              | Purpose                              |
| -------------------------------------------- | --------------------------------- | ------------------------------------ |
| `run_yudai_cli(args: List[str]) -> dict`     | `utils/run_yudai_cli.py`          | Execute CLI with PTY & timeout       |
| `run_agent(payload: dict) -> Iterator[dict]` | `swe_agent_integration/runner.py` | Stream SWE‑agent events              |
| FastAPI route `POST /api/run-cli`            | `main.py`                         | CLI execution endpoint               |
| FastAPI route `GET /`                        | `main.py`                         | Health check & API info              |

---

## 11. Dependencies

```txt
# FastAPI Backend (migrated from TypeScript)
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6

# SWE-agent integration
sweagent>=1.1.0

# Logging & utilities
simple-json-logger==0.4.1
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

*

---

## 17. Versioning & Commit Guidelines

(unchanged)

---

*End of Living PRD – auto‑consumed by CI/LLM agents.*
