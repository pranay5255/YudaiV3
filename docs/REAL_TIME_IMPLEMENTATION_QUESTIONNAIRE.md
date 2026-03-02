# Real-Time Session Implementation Questionnaire

Use this document to finalize requirements before implementation.

How to answer:
- Keep answers short and explicit.
- Use exact values where possible (timeouts, TTLs, limits, table names, endpoint paths).
- If unknown, write `TBD` and add who will decide.

---

## Cross-Phase Decisions

1. Confirm your six decisions are final for implementation (sandbox per org+repo+env, direct tunnel, SSE+WS split, PG on controller + sandbox cache, manual yudai-grep training script, persistence ends after issue+PR flow).  
Answer: yes keep all six decisions

2. How do you define `organization` in the system: GitHub org only, GitHub user namespaces too, or internal org entity?  
Answer:org is an internal entity and is filled in when the user signs in and chooses the git repo and branch 

3. Are forks treated as separate repos or linked to upstream sandbox identity?  
Answer:forks are currently treated as linked to upstream sandbox identity but this fucntionality is not supposed to be implemented now. 

4. What exactly is `environment` in sandbox keying: branch, deployment target, runtime profile, or combination?  
Answer:enviroment is the when the users signs with github and select a reppo and brach , we clone that repo/branch and setup that repo by asking user questions in chat. 

5. Final sandbox identity key: `org + repo + environment` only, or include additional dimensions?  
Answer: org + repo + environment

6. Who can access a shared sandbox: org members, repo collaborators, invited users, or role-based subsets?  
Answer: invited users, once the sandbox is live and conneLets implement this ater though

7. What roles/permissions are needed (viewer/chat/solver/pr-admin)?  
Answer:all permissions are given to the user once they sign in and select the repo and branch for now. 

8. What are your cost/concurrency caps per org/repo/environment?  
Answer:no caps for now as this is mvp

9. What are required SLOs (chat latency, solver stream latency, sandbox startup time)?  
Answer:chat latency: depends on LLM ineference, solver stream latency: 1s, sandbox startup time: 10s but can be more also

10. Which data is considered sensitive and needs extra controls?  
Answer:as of now no sensitive data is being stored, but users can add env vars to the UI which will be passed to the sandbox

---

## Phase 1: Controller + Sandbox Shell

11. Should we split into two deployables now (`controller` and `sandbox session server`) or keep one repo with two entrypoints first?  
Answer: we should keep one repo with two entrypoints first

12. Should existing API paths stay backward-compatible (`/api/daifu/...`) during migration?  
Answer:no not required

13. What exact controller endpoints should exist in v1 (create/get/delete sandbox, resolve tunnel, heartbeat, cleanup)?  
Answer:yes basic endpoints are required like "(create/get/delete sandbox, resolve tunnel, heartbeat, cleanup)". remember this is mvp

14. Should sandbox creation happen at session create, first chat, or first solve?  
Answer:session creation

15. Do you want pre-warming for popular repos/environments?  
Answer:no

16. What health checks should controller run against sandbox (interval, timeout, failure threshold)?  
Answer:liveness probe at 10s interval 

17. What exact metadata must be stored in PostgreSQL for sandbox lifecycle?  
Answer:basic metadata, you must use this for current db schema "/home/pranay5255/Documents/YudaiV3/backend/db/init.sql" and add addtional fields or tables if required for tracking and running sandboxes

18. Do you want a dedicated `sandboxes` table, `session_runtime` table, and `session_artifacts` table, or different schema names?  
Answer:yes i want dedicated tables for sandboxes, session_runtime, and session_artifacts

19. How should sandbox state transitions be modeled (`provisioning/running/degraded/stopped/terminated`)?  
Answer:provisioning/running/stopped/terminated

20. Should controller issue sandbox-scoped tokens, or reuse existing session JWT for direct tunnel auth?  
Answer:reuse existing session JWT for direct tunnel auth

21. Token TTL for tunnel access?  
Answer: 1 hour

22. Should tunnel tokens be one-time-use or reusable until expiry?  
Answer: reusable until expiry

23. Is token in SSE query param acceptable for Phase 1?  
Answer:yes

24. Required CORS origins for dev/staging/prod?  
Answer: https://yudai.app

25. Should controller still proxy requests as fallback when tunnel fails?  
Answer: no fail gracefully with error message

26. Where should sandbox cache be stored (path convention)?  
Answer: sandbox cache should be stored in the sandbox container at but must be transferred to /home/yudai/.cache/

27. Cache format preference now: JSON, JSONL, SQLite, or hybrid?  
Answer:JSON

28. Should cache writes be append-only for auditability?  
Answer: yes

29. What git sync policy inside sandbox: clone once + periodic fetch, pull on each operation, or webhook-driven?  
Answer: clone once + periodic fetch

30. What branch policy inside sandbox: shared branch, per-user branch, or per-solve branch?  
Answer:branch is selected by user at start with default as main

31. Can multiple users edit same working tree simultaneously in Phase 1?  
Answer:no

32. Should there be a repository lock during solve/PR creation?  
Answer:no

33. How should we detect "session complete" (exact event that ends persistence)?  
Answer:github issue creation is first criteria and secod criteria is pull request creation. Both must be fulfilled to end persistence.

34. After completion, delete immediately or keep grace period (minutes/hours) for debugging?  
Answer:yes delete immediately   

35. Should we export a final session artifact bundle before deletion in Phase 1?  
Answer:yes that is the artifact that is written to cache and finally to db

36. Required audit logs: who started sandbox, who solved, who created issue/PR, who terminated?  
Answer: termination is automatic after pull request creation everything else must be logged for audit purposes

37. Any compliance constraints (retention, deletion SLAs, encryption requirements)?  
Answer:not for now

---

## Phase 2: yudai-grep Activation

38. Where should the manual training script live (controller codebase, sandbox image, separate tooling dir)?  
Answer:controller codebase, here, this codebase

39. Preferred command shape (example CLI args you want)?  
Answer:simple scipt to train the model using the trajectories from session cache

40. Who is allowed to trigger training (admin only, repo maintainers, any collaborator)?  
Answer:admin only, for now only dev can

41. What training data sources are allowed (session trajectories, synthetic sets, issue text, code snapshots)?  
Answer:session trajectoris for now

42. Should data be filtered/anonymized before training?  
Answer:no

43. Where should checkpoints be stored (sandbox filesystem, object storage, both)?  
Answer:for now one model will be trained and used across all users and repos in the mvp

44. How do we version checkpoints (semantic version, timestamp, git SHA)?  
Answer:not required, will be manaul

45. Should sandbox always load latest successful model or pinned model per environment?  
Answer:not required

46. What is fallback behavior if model load fails at startup?  
Answer:hard failure with error message

47. What accuracy/quality gate is required before promoting a new model?  
Answer:not required for now. 

48. What latency budget for yudai-grep inference per query?  
Answer:not required for now. Will be handled by the myself

49. Do you want A/B comparison between old/new checkpoints before rollout?  
Answer:no will be done manually

50. Rollback mechanism: automatic on error threshold or manual only?  
Answer:not required for now. Will be handled by the myself

---

## Phase 3: Real-Time Streaming

51. Confirm exact split: SSE only for solver trajectory and WS only for chat.  
Answer:yes for now, suggest improvements for future, can we completely move to ws or SSE for consistency?

52. Should existing SSE event names/payloads remain compatible with current `TrajectoryViewer`?  
Answer:not required

53. Do you want `Last-Event-ID` resume support for SSE reconnects?  
Answer:no

54. Heartbeat interval for SSE?  
Answer:3s 

55. Max SSE stream duration before forced reconnect?  
Answer:10s

56. Required ordering guarantees for SSE events?  
Answer:not sure why this is needed

57. WebSocket endpoint path and auth handshake format?  
Answer: decide for yourself with best judgement

58. WS message schema: plain messages only or include token chunks, tool events, status events?  
Answer:plain message, tool events, token chunks and status events if changing

59. Should WS support chat history replay on reconnect?  
Answer:no

60. Backpressure strategy for fast token streams (drop, buffer, throttle)?  
Answer:choose and use your best judgement for mvp

61. Frontend reconnection policy (retry count/backoff/jitter)?  
Answer:retry count = 10

62. Should `TrajectoryViewer` support multiple concurrent solve runs in tabs?  
Answer: not required

63. Required UX when tunnel drops: auto-fallback to status polling or hard error?  
Answer:hard error

64. Do you want file-watch push notifications in this phase or postpone?  
Answer:postpone

65. What external changes should trigger file-watch events (git pull, branch switch, filesystem writes)?  
Answer:not required

---

## Phase 4: Advanced Features

66. For multi-user sessions, do you want shared presence indicators (who is connected)?  
Answer: yes shared presence indicators but later. Plan for this and add scaffolding 

67. Conflict resolution for concurrent edits: optimistic, lock-based, or branch-isolation?  
Answer:branch isolation

68. Parallel solver runs per sandbox: target max and queue policy?  
Answer:1 only for now

69. Should parallel solves share one repo working tree or isolated workdirs?  
Answer:parallel solves should share one repo working tree but are only available when multiple users connect to session

70. Persistent embeddings: store in sandbox FS, PostgreSQL/pgvector, or hybrid?  
Answer:pgvector

71. IDE integration scope: in-repo extension now or API-only foundation?  
Answer:not required for now will be implemented later

72. Repo-specific fine-tuning: still out-of-scope, or include design hooks now?  
Answer:repo specific fine tuning is out of scope for the user. This is a future feature that manually done by me in a separate repo. triggered manually

---

## Storage, Artifacts, and Data Lifecycle

73. Which object storage provider will hold traces/artifacts?  
Answer:aws s3 but has not been setup yet

74. Required artifact structure (trajectory, logs, patches, model metadata)?  
Answer:trajectory, logs. Patches are stored as github PRs in github.

75. Key naming convention for artifacts?  
Answer:decide for yourself with best judgement

76. Retention policy for artifacts and metadata?  
Answer:ont sure what this means. ignore for now

77. Do you need per-org data residency controls?  
Answer:no

78. Should metadata in PG include object-store checksums/ETags for integrity?  
Answer:yes

---

## Security

79. Should direct tunnel require signed short-lived URLs in addition to auth token?  
Answer:yes

80. Any IP allowlisting or VPN constraints?  
Answer:no

81. Secret injection method for sandbox (env vars, secret manager, mounted files)?  
Answer:modal sanbox provides fucntionality to inject env vars but can only be triggered at sandbox start

82. Do you require tamper-evident audit logs?  
Answer:no

83. Any threat model requirements we must explicitly satisfy before rollout?  
Answer:no

---

## Testing, Rollout, and Operations

84. Required test coverage by phase (unit/integration/e2e/load)?  
Answer:integration and e2e

85. Required load test profile (concurrent users, concurrent sandboxes, stream duration)?  
Answer:not required for now

86. Observability stack preference (logs, metrics, traces tooling)?  
Answer:not required for now in mvp

87. Critical alerts you want on day 1?  
Answer:not required for now in mvp, manual monitoring

88. Rollout strategy: internal org first, allowlist orgs, or feature flag by repo?  
Answer:internal org first

89. Migration strategy for existing sessions during cutover?  
Answer:not required for now in mvp

90. Rollback strategy per phase?  
Answer:not required for now in mvp

91. Timeline targets for each phase (start/end dates)?  
Answer: implement everything now

92. Who owns each area (controller, sandbox server, frontend streaming, ML training, infra)?  
Answer: all me

93. What is your "definition of done" for each phase?  
Answer: deep testing and manual testing in browser. 

94. Which items are hard blockers vs nice-to-have?  
Answer: whichever is a blocker for now should be ignored

