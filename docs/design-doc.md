# YudaiV3 UI Refactor Design Doc

## Updated
- March 12, 2026

## Purpose
- Make the landing page in [`src/components/LoginPage.tsx`](/home/yudai/YudaiV3/src/components/LoginPage.tsx) the canonical visual system for the full app.
- Use this document to refactor the authenticated workspace so it matches the landing page logo treatment, surfaces, colors, spacing, and hierarchy.
- Preserve product behavior. This is a UI system and presentation refactor guide, not a workflow or API redesign.

## Canonical Source Files
- Visual source of truth: [`src/components/LoginPage.tsx`](/home/yudai/YudaiV3/src/components/LoginPage.tsx)
- Base theme tokens: [`src/index.css`](/home/yudai/YudaiV3/src/index.css)
- Tailwind token mapping: [`src/tailwind.config.js`](/home/yudai/YudaiV3/src/tailwind.config.js)
- Primary logo asset: [`src/public/assets/baseLogo.png`](/home/yudai/YudaiV3/src/public/assets/baseLogo.png)
- Main workspace shell to migrate:
  - [`src/components/TopBar.tsx`](/home/yudai/YudaiV3/src/components/TopBar.tsx)
  - [`src/components/Sidebar.tsx`](/home/yudai/YudaiV3/src/components/Sidebar.tsx)
  - [`src/components/Chat.tsx`](/home/yudai/YudaiV3/src/components/Chat.tsx)
  - [`src/components/ContextCards.tsx`](/home/yudai/YudaiV3/src/components/ContextCards.tsx)
  - [`src/components/TrajectoryViewer.tsx`](/home/yudai/YudaiV3/src/components/TrajectoryViewer.tsx)
  - [`src/components/SolveIssues.tsx`](/home/yudai/YudaiV3/src/components/SolveIssues.tsx)
  - [`src/components/RepositorySelectionToast.tsx`](/home/yudai/YudaiV3/src/components/RepositorySelectionToast.tsx)
  - [`src/components/Toast.tsx`](/home/yudai/YudaiV3/src/components/Toast.tsx)

## Brand Direction

### Product posture
- Enterprise engineering system, not a hacker-terminal toy.
- The UI should communicate control, auditability, and review confidence.
- The app should feel precise and operational, but never cramped or noisy.

### Visual language
- Dark atmospheric backdrop.
- Deep navy surfaces layered over near-black page background.
- White text for priority content, muted zinc text for support copy.
- Cyan, sky, and emerald as the active accent family.
- Large radii, soft borders, blurred glass fills, and restrained glows.

### What to avoid
- Do not lead the app with amber as the global accent color.
- Do not default to mono typography for navigation, headings, or body copy.
- Do not use flat gray panels when a layered dark surface is expected.
- Do not rebuild the brand using a `Y3` badge where the logo should appear.

## Logo System

### Primary logo
- Always use [`/assets/baseLogo.png`](/home/yudai/YudaiV3/src/public/assets/baseLogo.png) as the brand mark.
- The logo should sit inside a framed lockup, not directly on the page background.
- Use the landing page lockup as the reference implementation:
  - Background shell: `#051425`
  - Shape: rounded `24px` to `28px`
  - Border: `1px solid rgba(255,255,255,0.10)`
  - Shadow: deep soft shadow, approximately `0 24px 60px rgba(0,0,0,0.35)`
  - Accent lighting: subtle cyan and sky radial highlights behind the logo

### Logo sizing
- Hero / marketing placement: `240px` to `300px` wide
- Sidebar / top bar brand placement: `132px` to `168px` wide
- Compact mobile shell: scaled lockup, never an improvised text badge

### Logo usage rules
- Keep generous empty space around the logo container.
- Do not crop the logo aggressively.
- Do not add extra text labels inside the same lockup unless the surface is truly space-constrained.
- If a collapsed navigation needs an icon-only state, use a cropped logo treatment derived from the real logo, not the current amber `Y3` square.

## Color System

### Existing foundation tokens
These already exist in [`src/index.css`](/home/yudai/YudaiV3/src/index.css) and should remain the base semantic palette:

| Token | Value | Use |
|---|---|---|
| `--bg-primary` | `#0a0a0b` | page background |
| `--bg-secondary` | `#111113` | secondary shell background |
| `--bg-tertiary` | `#1a1a1d` | nested or utility surfaces |
| `--text-primary` | `#f4f4f5` | main text |
| `--text-secondary` | `#a1a1aa` | supporting text |
| `--text-muted` | `#71717a` | labels, metadata |
| `--accent-cyan` | `#22d3ee` | info, live state, focus |
| `--accent-emerald` | `#10b981` | success, health, ready |
| `--accent-amber` | `#f59e0b` | warning, pending, caution only |
| `--accent-error` | `#ef4444` | destructive and error |
| `--discord` | `#5865f2` | Discord CTA only |

### Landing-page-only surface colors now promoted to shared app usage
- `#051425`: primary brand shell for logo frames and high-importance brand surfaces
- `#08111d`: default elevated enterprise panel background
- `rgba(255,255,255,0.03)` to `rgba(255,255,255,0.05)`: glass fill for cards and pills
- `rgba(255,255,255,0.10)`: default border for cards, shells, and dividers
- `sky-400` equivalent `#38bdf8`: secondary accent in gradients and active states

### Background recipe
- Page base stays near-black.
- Add a top-to-bottom dark gradient overlay similar to the landing page:
  - `rgba(5,12,24,0.92)` into `rgba(10,10,11,0.96)`
- Add a faint grid pattern and two soft blur blooms:
  - cyan bloom on the left or lower-left
  - emerald bloom on the right or upper-right

### Accent usage rules
- `Cyan / sky`: selection, live activity, tabs, focus, info states, telemetry
- `Emerald`: success, ready status, verified state, completion, trust markers
- `White`: highest-priority CTA, especially primary action buttons
- `Amber`: reserved for warnings, in-progress solve actions, or cautionary actions
- `Red`: errors and destructive states

### Refactor implication
- The authenticated workspace is currently too amber-forward.
- Refactoring should shift the app from amber-led navigation toward cyan / sky / emerald-led navigation and status.
- Amber should remain available, but not as the dominant personality of the shell.

## Typography

### Font roles
- Primary UI font: `sans` / Inter
- Utility font: `mono` / JetBrains Mono

### Rules
- Use `sans` for headlines, section titles, navigation labels, panel titles, buttons, and body content.
- Use `mono` only for:
  - compact counters
  - step numbers
  - technical identifiers
  - branch names, session ids, or code-like chips where that distinction adds meaning
- The current workspace overuses mono. That should be reduced during refactor.

### Type scale guidance
- Hero headlines: bold, dense tracking, large clamp sizing
- Section titles: `text-2xl` to `text-3xl`, negative tracking
- Card titles: `text-sm` to `text-lg`, semibold
- Body: `text-sm` to `text-lg`, line-height `1.6` to `1.8`
- Eyebrows and metadata: uppercase with wide tracking, similar to `tracking-[0.24em]`

## Shape, Borders, and Depth

### Shape system
- Pills: fully rounded or `rounded-full`
- Standard controls: `rounded-2xl`
- Primary cards: `rounded-[24px]`
- Large shells and hero frames: `rounded-[30px]` to `rounded-[32px]`

### Borders
- Prefer `border-white/10` over opaque gray borders for premium surfaces.
- Only use solid semantic borders for alerts and high-signal status callouts.

### Shadows
- Surfaces should use long, soft shadows rather than harsh drop shadows.
- Typical shadow profile:
  - `0 24px 60px rgba(0,0,0,0.24)` for content panels
  - `0 30px 80px rgba(0,0,0,0.32)` or higher for hero shells

### Blur and glass
- Backdrop blur is part of the design language.
- Use it for cards, floating panels, toasts, and sticky bars when they sit on the dark background.
- Keep opacity low so the UI remains crisp.

## Layout Principles

### Desktop layout
- Use `max-w-7xl` content width.
- Keep primary narratives in wide open compositions.
- Allow one high-value visual focus element per screen to occupy substantial real estate.

### Centerpiece rule
- The most important visual explanation element should sit in the center on large screens.
- The landing page workflow preview is the reference:
  - centered on desktop
  - approximately `40vw` wide at extra-large breakpoints
  - prominent enough to occupy around 40 percent of the first-screen attention

### Spacing
- Card padding should generally be `20px` to `32px`.
- Use large vertical rhythm between major sections.
- Avoid dense dashboard packing until the app has established hierarchy.

## Motion

### Keep
- Small pulse indicators for live status
- `150ms` to `300ms` hover / focus / press transitions
- Translate and opacity motion only

### Avoid
- Big springy animations
- Permanent glowing animation on all active elements
- Width / height animation for layout-critical panels

## Component System Rules

### Buttons

#### Primary
- White fill
- Dark text
- Large rounded corners
- Slight lift on hover
- Used for highest-priority actions such as sign-in or confirm

#### Secondary
- Glass fill `bg-white/[0.04]`
- White border at low opacity
- White text
- Used for install, alternative actions, and lower-priority actions

#### Semantic
- Cyan-tinted: informational and live-state toggles
- Emerald-tinted: success or verified actions
- Amber-tinted: cautionary or in-progress solve actions
- Red-tinted: destructive actions

### Pills and status chips
- Use pill surfaces with muted text for metadata.
- Live dots should be cyan or emerald, not amber by default.
- Status tone should read from accent + surface tint, not just text color.

### Cards
- Default card background: `#08111d` or white glass overlay over the dark page
- Rounded `24px+`
- Border `white/10`
- Clear internal hierarchy:
  - eyebrow
  - title
  - support copy
  - action row

### Forms
- Form shells should match the landing page onboarding card.
- Inputs should move away from plain gray blocks and into dark elevated fields with soft borders.
- Validation should be inline and visually consistent with alert cards.

### Modals and toasts
- Use floating glass panels with deeper blur and larger radii.
- Toasts should inherit the same surface style instead of looking like separate utilitarian system UI.
- Keep icon, title, and message aligned with the landing page spacing scale.

## Workspace Refactor Mapping

### Sidebar
Current problem:
- [`src/components/Sidebar.tsx`](/home/yudai/YudaiV3/src/components/Sidebar.tsx) still uses a terminal-style `Y3` badge, mono-heavy labels, gray shell, and amber-led active states.

Target:
- Replace the `Y3` badge with a compact real-logo lockup.
- Use a dark layered shell closer to the landing page panel language.
- Change active states from amber-heavy to cyan / sky-led.
- Use `sans` for nav labels and reserve mono for tiny utility text only.
- Keep collapsed navigation clean and brand-consistent.

### Top Bar
Current problem:
- [`src/components/TopBar.tsx`](/home/yudai/YudaiV3/src/components/TopBar.tsx) still reads like a terminal dashboard bar with hard-coded amber emphasis and compact utility styling.

Target:
- Turn the header into a premium blurred surface.
- Use the logo lockup or a compact brand block on the left.
- Make repository and workspace metadata feel secondary, not visually equal to the title.
- Convert tab buttons into landing-page-style pills with a cyan / sky active treatment.
- Status chips should use the landing accent family and white/10 borders.

### Main content surfaces
Applies to:
- [`src/components/Chat.tsx`](/home/yudai/YudaiV3/src/components/Chat.tsx)
- [`src/components/ContextCards.tsx`](/home/yudai/YudaiV3/src/components/ContextCards.tsx)
- [`src/components/TrajectoryViewer.tsx`](/home/yudai/YudaiV3/src/components/TrajectoryViewer.tsx)
- [`src/components/SolveIssues.tsx`](/home/yudai/YudaiV3/src/components/SolveIssues.tsx)

Target:
- Replace flat zinc panels with layered navy panels and glass cards.
- Promote clearer section titles and supporting descriptions.
- Increase border radius and reduce hard utility styling.
- Use cyan and emerald to show activity and success, keeping amber for cautionary solve flows only.

### Repository selection and modal flows
Applies to:
- [`src/components/RepositorySelectionToast.tsx`](/home/yudai/YudaiV3/src/components/RepositorySelectionToast.tsx)
- [`src/components/Toast.tsx`](/home/yudai/YudaiV3/src/components/Toast.tsx)

Target:
- Match the onboarding card aesthetic from the landing page.
- Use card framing, soft blur, and stronger hierarchy.
- Remove the feeling of an unrelated system popup.

## Element-Level Refactor Rules

### Navigation
- Tabs should read as pills, not terminal toggles.
- Active tab:
  - tinted cyan or sky background
  - brighter border
  - white text
  - optional subtle glow
- Inactive tab:
  - glass fill
  - muted text
  - visible hover state

### Data cards
- Give each card a clear title and supporting sentence.
- Use semantic accent blocks sparingly.
- Use dark inner surfaces inside larger glass shells when a card needs nested content.

### Empty states
- Move away from generic gray placeholders.
- Use one accent icon, a short sentence, and one primary action.
- Keep spacing generous and typography clean.

### Alerts
- Error: red border plus red-tinted background at low opacity
- Info: cyan tint
- Success: emerald tint
- Alerts should retain the same border radius and surface logic as the rest of the UI

## Suggested Token Additions
These are not implemented yet, but should be added when the broader refactor starts:

| Proposed token | Suggested value | Purpose |
|---|---|---|
| `--surface-brand` | `#051425` | logo shells and high-importance brand surfaces |
| `--surface-elevated` | `#08111d` | standard elevated card background |
| `--surface-glass` | `rgba(255,255,255,0.04)` | default glass fill |
| `--border-soft` | `rgba(255,255,255,0.10)` | shared premium border |
| `--accent-sky` | `#38bdf8` | second active accent |
| `--overlay-top` | `rgba(5,12,24,0.92)` | background gradient start |
| `--overlay-bottom` | `rgba(10,10,11,0.96)` | background gradient end |

## Refactor Order

### Phase 1: Shared shell
1. Update global background and surface tokens in [`src/index.css`](/home/yudai/YudaiV3/src/index.css).
2. Refactor [`src/components/Sidebar.tsx`](/home/yudai/YudaiV3/src/components/Sidebar.tsx) to adopt the real logo and new active-state system.
3. Refactor [`src/components/TopBar.tsx`](/home/yudai/YudaiV3/src/components/TopBar.tsx) to the landing-page surface language.

### Phase 2: Shared primitives
1. Normalize buttons, pills, alerts, cards, and form fields.
2. Update toast and modal surfaces.

### Phase 3: Feature pages
1. Refactor chat panels and composer
2. Refactor context cards
3. Refactor trajectory viewer
4. Refactor solve issues flow

## Non-Negotiables
- Do not change auth behavior.
- Do not change session state behavior.
- Do not change routes or API contracts as part of the visual refactor.
- Do not introduce a second competing visual language.
- The landing page is now the visual source of truth for the rest of the app.
