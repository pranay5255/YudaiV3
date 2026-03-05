# YudaiV3 Enterprise Landing + Intro Video Design Doc

## Date
- March 5, 2026

## Scope
- Embed the Remotion intro video on the landing/login page.
- Reposition landing copy from founder-first to enterprise-ready value.
- Preserve all existing auth functionality (`handleGitHubLogin`, OAuth flow, GitHub App install logic, loading/error behavior).

## Source Inputs
- `docs/3-MODE-IMPLEMENTATION-PLAN.md`
- `docs/REAL_TIME_IMPLEMENTATION_QUESTIONNAIRE.md`

## Skills Used
- `ui-ux-pro-max`: hierarchy, clarity, conversion-first content architecture.
- `vercel-react-best-practices`: React-safe edits with unchanged behavior.
- `remotion-best-practices`: intro video composition and rendering standards.

## Positioning Shift
- From: solo-dev/founder velocity language.
- To: enterprise engineering platform language.

### Enterprise Value Pillars
1. Governed delivery pipeline
   - Architect -> Tester -> Coder modes produce deterministic issue-to-PR flow.
2. Traceability and compliance support
   - Auditable trajectory logs and artifact trail.
3. Runtime isolation and control
   - Sandbox identity keyed by `org + repo + environment`.
4. Operational visibility
   - Real-time WebSocket + SSE status streaming.

## Intro Video Embed Specification
- Video asset: `/videos/yudai-enterprise-intro.mp4`
- Placement: right side of hero on desktop, stacked below hero text on mobile.
- Framing:
  - Rounded terminal-card shell with subtle gradient border.
  - Muted autoplay + loop + playsInline for frictionless preview.
  - Supporting caption emphasizing live trajectory and enterprise review confidence.

## Landing Copy System (Enterprise)

### Hero
- Eyebrow: `enterprise-ready delivery orchestration`
- Headline: `From requirement to issue, tests, and review-ready PRs.`
- Subheadline: policy-aware GitHub workflow with full execution traceability.

### Hero Chips
- `Governed Architect -> Tester -> Coder flow`
- `Audit-ready trajectory and artifact trail`
- `Org-scoped sandbox runtime controls`

### How It Works
1. `Provision`: select org/repo/branch, initialize controlled runtime.
2. `Specify`: Architect mode generates scoped implementation issue.
3. `Assure`: Tester mode writes tests before coding.
4. `Deliver`: Coder mode implements, validates, and opens PR with traceability.

### Capabilities Grid
- Multi-mode orchestration
- Sandbox identity isolation
- Real-time operational telemetry
- Issue-to-PR lifecycle gating
- Audit artifacts and logs
- GitHub-native enterprise controls

### Right Login Panel
- Keep 2-step auth flow, but enterprise framing copy.
- Do not change button behavior, handlers, URLs, or error/loading logic.

### Bottom CTA
- Reinforce enterprise outcomes: governance, reliability, visibility, and review confidence.

## Non-Negotiables
- No auth logic changes.
- No route or API changes.
- Content and presentation updates only.
