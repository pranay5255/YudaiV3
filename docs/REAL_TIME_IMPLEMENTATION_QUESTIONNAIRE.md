# Real-Time Session Implementation Questionnaire

Use this document to finalize requirements before implementation.

How to answer:
- Keep answers short and explicit.
- Use exact values where possible (timeouts, TTLs, limits, table names, endpoint paths).
- If unknown, write `TBD` and add who will decide.

---

## Cross-Phase Decisions

1. Confirm your six decisions are final for implementation (sandbox per org+repo+env, direct tunnel, SSE+WS split, PG on controller + sandbox cache, manual repo-helper training script, persistence ends after issue+PR flow).
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

## Phase 2: Legacy Repo-Helper Activation

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

48. What latency budget for legacy repo-helper inference per query?
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

70. Persistent embeddings: store in sandbox FS, relational DB, or hybrid?
Answer: legacy answer removed with the indexing path

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

----------------------------------------------------------------------------------------

3 MODE IMPLEMENTATION Questions

Block 1 — How the User Triggers Execution

  Q1. What does the user currently do in the UI to start the 3-mode pipeline? Is it:
  - (a) They type a natural language message in chat and the pipeline auto-fires
  - (b) There's a dedicated "Run" button (the SolveIssues.tsx component)
  - (c) They paste a GitHub issue URL and hit run
  - (d) Something else

  A1 - the 3 mode pipeline is a sequential pipeline to create reliable code in codebases. After the user connects their repo in the chat window, They are automatically in the 1st mode which is ARCHITECT. The architect mode is supposed create a github issue for the user's requirement. To acheive this task the architect is the only mode which inetrfaces with the user and answers the questions the user has. It in turn asks MCQ questions to the user to get detailed context from the user about the problem they are trying to solve. 

  Q2. The execution endpoint receives an objective: str. Where does that string come from in the UI — is
  it the last chat message, a separate text field, a selected GitHub issue, or all three depending on
  context?

  A2 - Execution endpoint gets a mini-swe-agent command with a custom config. There will be three custom configs for each mode. We will brainstorm on how these configs will differ from each other on the user's repo after cloning to establish what is the objective we are trying to achieve for the user. The strng comes from a separate python file which includes the config file and the prompt required and the final bash command to run in the sandbox.  

  Q3. Right now the user flow goes: select repo → create session → (chat?) → click execute. Is the chat
  step mandatory before execution, or can the user skip straight to execution after session creation?

  A3 - Chat is the interface where the user interacts to provide context or answer questions also for addtional context required. Going from 1 mode to the next mode requires the user to answer some questions or provide enough context. Execution happens on the sandbox and questions and interactivity and context is supposed to be happen using the chat.

  ---
  Block 2 — What Happens Inside Each Mode (Your Mental Model)

  Q4. For Architect mode: the MSWEA agent runs, explores the repo, and creates a real GitHub issue. After
  it finishes, the pipeline auto-moves to Tester. Is that correct, or do you want the user to
  review/approve the created issue before Tester starts?

  A4 - The architect mode is a two sided module. On one side it explores the repo in the sandbox and creates a set of releevant questions that it does not have answer to or needs addtional context from the user.The questions are gathered from the architect and given to the frontend to gather context from the user. Once the user answers questions, we let the user create an issue from the /create-issue endpoint. Then we move onto the Tester mode.

  Q5. For Tester mode: the agent writes tests and commits them to a branch like yudai/issue-123-tests. The
   branch name is parsed from stdout. Two sub-questions:
  - (a) Should the agent always commit tests to a deterministic branch (yudai/issue-{number}-tests) so the
   backend can predict it, or should it be parsed from output?
  - (b) Should tester run against the base branch, or does it need the issue to exist first in GitHub?

  A5 - Tester or Architect or Coder works in a separate branch on the repo. We must create a separate branch when we lone the repo. Once that is done, we must make sure that the github issue has been created by the ARchitect mode. This is important as the architect mode has the context and the acceptance criteria from the user which lets the tester write the tests for that github issue. We make sure that these tests written by the tester are exclusive and only concern the github issue at hand. These tests must pass after the Implementation is done by the Coder.

  Q6. For Coder mode: the agent implements the fix, runs the test branch, and opens a PR. Does the PR need
   to pass tests before the pipeline considers it complete, or is "PR opened" sufficient for the session
  to end?

  A6 - yes, read above A5.

  ---
  Block 3 — GitHub Token & Credentials in Sandbox

  Q7. When the sandbox runs, the MSWEA agent needs to call gh issue create and gh pr create. Looking at
  the code, the GitHub token is fetched from AuthToken and passed into _ensure_runtime_ready as an env
  var. Do you know if GITHUB_TOKEN is actually being passed into the Modal sandbox environment when it's
  provisioned? This is critical — without it, issue/PR creation silently fails.

  A7 - Issue creation is ahndled by the controller endpoints to create the github issue. But the github token must be apssed into the sansdbox so it can create a Pull request for the corresponding github isse. The tester mode is usually just commits the tests required in the branch created.

  Q8. The MSWEA config has mode: confirm — this may cause the agent to pause and ask for human
  confirmation mid-run, which would hang the pipeline. Did you intend it to be fully automated
  (--yolo-mode is already in the command, which should override this)? Do you know if --yolo-mode disables
   the mode: confirm behavior in your version of minisweagent?
  A8 -Some modes are fully automated like tester, some modes are defined in the config which are like architect which ask for feedback from the user before proceeding. Coder is also automated.  

  ---
  Block 4 — What the User Sees While Running (Streaming UX)

  Q9. The backend sends SANDBOX_STREAM WS events for every stdout/stderr line from the agent. On the
  frontend, where does this output go? Is it:
  - (a) The existing TrajectoryViewer component
  - (b) Shown inline in the chat as a progress stream
  - (c) A separate panel/drawer
  - (d) Not yet wired — it's sent but not displayed
  A9 - This goes into TrajectoryViewer component. There are two tabs the trajectory is where is the execution displayed.

  Q10. While a mode is running, what should the user see for mode-level progress? For example:
  - A stepper showing [Architect ✓] [Tester ⟳] [Coder ○]
  - A progress bar per mode
  - Just the raw agent output stream
  - A combination
   A10 - A progress bar per mode in the header of the app. This should look nice as a progress bar.

  Q11. The backend sends MODE_EVENT WS messages when each mode starts (mode: "architect", state:
  "running") and when it completes. Is the frontend currently listening for MODE_EVENT and doing anything
  with it, or is that handler not built yet?
  A11 - No it is not. HElp me decide how to solve this and what are your suggestions for this. 
  ---
  Block 5 — Error Handling & Recovery

  Q12. If Architect mode fails (agent exits non-zero, or can't parse issue URL from output), what should
  happen?
  - (a) Whole pipeline fails, user sees error, can retry from scratch
  - (b) User can retry just Architect
  - (c) User can override with a manually-provided issue URL and resume from Tester
  - (d) Not decided yet
  A12 - Architect mode restarts to help user create the github issue. 

  Q13. If the sandbox goes away mid-pipeline (Modal timeout, network drop), _ensure_runtime_ready will
  re-provision a new sandbox. Does the new sandbox have the repo already cloned, or does it start from
  scratch? Does the pipeline retry from the failed mode or from the beginning?

  A13 - It starts from scratch and restarts from github issue creation. If issue already created then we ask the user to select the github issue. And restart from Tester. 

  Q14. The coder mode currently raises RuntimeError if it can't parse a PR URL from stdout. If the agent
  creates the PR but the output parsing fails (e.g. the agent doesn't print the URL), the pipeline crashes
   even though GitHub has the PR. Is strict parsing acceptable, or do you want a fallback (e.g. call the
  GitHub API to find the latest PR)?
  A14 - HElp me with what is the right direction. Here the coder mode is supposed to create a PR after the patch iimplemented by the agent and test suite run. If tests pass then we create a PR using execution endpoint. OR the agent can also create the PR from within the sandbox execution. 
  ---
  Block 6 — The MSWEA Agent & Config

  Q15. The three config files all use identical workflow steps ("analyze codebase → create script → edit
  source → verify fix"). Only the system_template role description differs. Is this intentional for now,
  or do you want mode-specific instructions? For example:
  - Architect: "do NOT edit code, only create a GitHub issue"
  - Tester: "write tests only, commit to branch yudai/issue-{number}-tests, do NOT implement the fix"
  - Coder: "implement the fix, run the tests from branch, open PR"

  A15 - Yes, help me brainstorm things that need to change in the config files for each mode. And what execution orders need to be handled whenintermediate transitioning steps from  one mode to another using the execution endpoint. HElp me with suggestions.

  Q16. The command uses python -m mswea.solve but the docs say python -m minisweagent.solve. Which module
  name is correct in your installed version of the agent?

 A16 - i think minisweagent is correct. Help me figure this out from the docs for mswea https://mini-swe-agent.com/latest/. Go through the docs deeply.

  Q17. step_limit: 0 in the configs — does 0 mean unlimited steps, or does it mean 0 steps allowed (which
  would immediately exit)? What step limit do you want per mode?

  A17 - Step_limit must be 15 for now. 





