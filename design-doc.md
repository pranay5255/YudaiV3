# YudaiV3 Landing Page Redesign

## Workspace UI Update (February 2026)

### Scope Implemented

This update expands beyond the login/landing view and standardizes the in-app workspace shell, chat view, and solve-issues board.

### Interaction and Reliability Fixes

1. **Context card deletion ownership fixed**
   - `ContextCards` no longer deletes directly.
   - Parent (`App`) is now the single owner of deletion side effects and toast feedback.

2. **Trajectory stream status correctness**
   - SSE close/disconnect no longer overwrites terminal status.
   - `completed` and `error` states are preserved correctly.

3. **Session error classification hardened**
   - Session recovery now keys off explicit error codes and strict patterns.
   - Removed broad `"session"` substring matching to avoid accidental session clears.

4. **Zustand rerender pressure reduced**
   - Replaced full-store subscriptions with selector + `useShallow` patterns in repository/session hooks and repository picker surfaces.

5. **Solver endpoint consistency**
   - Solver `status` and `cancel` paths are now centralized through `src/config/api.ts` and consumed via `buildApiUrl(...)`.

6. **Model selection behavior**
   - Solve modal now auto-selects **only free models** when available.
   - If no free model exists, user must explicitly choose a model.

### Visual Hierarchy Improvements

1. **TopBar redesigned into a true two-tier command surface**
   - Primary tier: workspace identity, repository context, session state, indexing toggle, auth control.
   - Secondary tier: task navigation tabs + compact message/context counters.
   - Added subtle directional gradient and stronger status grouping.

2. **Solve Issues board information architecture upgraded**
   - Added summary chips (Total / Yudai / Other) in header.
   - Filter controls rebalanced with clearer affordance.
   - Issue cards now emphasize:
     - state + issue number first,
     - title second,
     - description and labels third,
     - metadata row (opened date/comments) last.

3. **Chat view readability refinement**
   - Header now expresses conversation context and live session readiness explicitly.
   - Message bubbles include role labels (`Assistant`, `You`, `System`) for faster scanning.
   - Input key handling upgraded to `onKeyDown` + composition-safe enter behavior.

### Design Token and Utility Stabilization

To remove class/token drift and keep legacy utility usage working safely:

- Added color aliases (`bg`, `fg`, `primary`, `muted`) in `tailwind.config.js`.
- Added missing custom utilities in `src/index.css`:
  - `terminal-noise`
  - `shadow-terminal`
  - `glow-amber`
  - `glow-cyan`
  - `glow-emerald`
  - `border-3`

This preserves the established "Terminal Precision" visual language while making class usage deterministic and maintainable.

## Design Brief

**App Definition:**
YudaiV3 is a context-engineered coding agent that connects to your GitHub repo and turns curated chat summaries, file-dependency insights, and analytics into small, review-ready PRs, while logging auditable trajectories.

---

## Design Direction

### Aesthetic: "Terminal Precision"

A refined, developer-focused aesthetic that blends the familiar comfort of terminal interfaces with sophisticated typography and subtle depth. Think: the confidence of a well-crafted CLI tool meets the polish of premium developer tooling.

**Key Characteristics:**
- Monospace-inspired typography hierarchy with a distinctive display font
- Deep charcoal/obsidian backgrounds with warm amber and cyan accents
- Subtle scan-line textures and terminal-inspired visual motifs
- Clean geometric shapes with precise spacing
- Understated animations that feel responsive, not flashy

### Color Palette

```css
--bg-primary: #0a0a0b        /* Near-black obsidian */
--bg-secondary: #111113      /* Elevated surfaces */
--bg-tertiary: #1a1a1d       /* Cards and containers */
--border: #2a2a2e            /* Subtle borders */
--border-accent: #3d3d42     /* Emphasized borders */

--text-primary: #f4f4f5      /* Primary text */
--text-secondary: #a1a1aa    /* Secondary text */
--text-muted: #71717a        /* Muted text */

--accent-amber: #f59e0b      /* Primary accent - warm, trustworthy */
--accent-amber-soft: #f59e0b20
--accent-cyan: #22d3ee       /* Secondary accent - technical, precise */
--accent-cyan-soft: #22d3ee15
--accent-emerald: #10b981    /* Success states */
```

### Typography

**Display/Headlines:** JetBrains Mono or IBM Plex Mono - technical credibility
**Body Text:** Inter or system-ui - clean readability
**Accents:** Monospace for technical terms and feature labels

---

## Content Architecture

### Hero Section
- **Headline:** "Context-Engineered PRs"
- **Subheadline:** Emphasizes the transformation: chat + files + insights → review-ready PRs
- **Visual:** Abstract representation of context flowing into code

### Value Propositions (3 Pillars)

1. **Connect Your Repo**
   - GitHub integration
   - File dependency mapping
   - Automatic context extraction

2. **Curate Context**
   - Chat summaries capture intent
   - File insights inform scope
   - Analytics guide decisions

3. **Ship Small PRs**
   - Review-ready code changes
   - Auditable trajectories
   - Traceable decision logs

### How It Works (Process Flow)

1. **Ingest** — Connect repo, extract file dependencies and structure
2. **Converse** — Chat captures intent; context cards distill key insights
3. **Generate** — Agent produces focused, small PRs from curated context
4. **Audit** — Every decision logged with full trajectory for review

### Feature Highlights

- File dependency analysis
- Curated chat summaries
- Context card system
- Small, focused PRs
- Auditable trajectories
- Analytics-driven insights

---

## Component Structure (Preserved)

### Functionality to Keep Unchanged:
- `handleGitHubLogin()` function and all its logic
- `githubAppInstallUrl` computation
- Error parameter handling from URL
- Loading states and button disabled states
- GitHub OAuth button with icon
- GitHub App installation link
- Discord community link
- Terms of service footer

### Layout Changes:
- Hero section: New copy, refined typography
- Left column: Updated value props and features
- Right column: Same structure, updated copy
- Bottom CTA: Updated messaging

---

## Visual Details

### Texture & Depth
- Subtle noise overlay on dark backgrounds (2-3% opacity)
- Faint horizontal scan lines for terminal feel
- Soft glow effects around accent elements
- Border gradients for depth perception

### Micro-interactions
- Smooth button hover states with subtle lift
- Gentle pulse on step indicators
- Fade-in animations on scroll (staggered)
- Terminal cursor blink on hero accent

### Iconography
- Simple line icons for features
- GitHub logo preserved as-is
- Custom connection/flow indicators

---

## Implementation Notes

1. Use CSS custom properties for theming consistency
2. Keep Tailwind for utility classes, add custom styles for unique elements
3. Preserve all React state and event handlers exactly
4. Font loading via Google Fonts link or system fallbacks
5. Animations via CSS transitions (no external libraries needed)
