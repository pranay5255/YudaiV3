# React 19 Upgrade + CLI-Inspired Design Revamp

## Overview

Upgrade React 18.3.1 → 19.x and enhance the Terminal Precision design system with CLI-inspired chat interface improvements. Current codebase is well-positioned for this upgrade with modern patterns and 80% design system completion.

**Estimated Time:** 14-19 hours across 4-5 days
**Risk Level:** Low-Medium (no deprecated APIs found)
**User Goal:** CLI-inspired chat UI like modern coding tools

### Docker Production Compatibility ✅

**Current Setup:** docker-compose.prod.yml
- Frontend: Node 18-alpine → Vite build → nginx static serving
- Build: `npm ci && npm run build` in Docker
- Output: Static HTML/CSS/JS (version-agnostic)

**React 19 Compatibility:**
- ✅ Node 18 supports React 19 (min: 18.17.0)
- ✅ No Dockerfile changes needed
- ✅ Same build process (npm ci → build → dist/)
- ✅ Static output served by nginx (unaffected)
- ✅ Health checks unchanged
- ✅ Environment variables unaffected

**Risk:** NONE - React upgrade is transparent to Docker

---

## Phase 1: React 19 Upgrade (3-4 hours)

### 1.1 Preparation
```bash
git checkout -b upgrade/react-19-cli-design
npm test  # Baseline
npm run build  # Note bundle sizes
```

### 1.2 Dependency Updates
```bash
# Core React
npm install react@19 react-dom@19

# Type definitions
npm install -D @types/react@19 @types/react-dom@19

# Vite plugins (optional update)
npm install -D @vitejs/plugin-react@latest @vitejs/plugin-react-swc@latest
```

**Already React 19 Compatible:**
- ✓ @tanstack/react-query ^5.85.5
- ✓ react-router-dom ^7.8.2
- ✓ zustand ^5.0.8
- ✓ lucide-react ^0.344.0

### 1.3 Breaking Changes Assessment

**Good News:** Exploration found ZERO breaking changes needed!
- ✓ Using createRoot (modern API)
- ✓ No PropTypes, defaultProps, or legacy APIs
- ✓ No string refs
- ✓ Modern JSX transform configured
- ✓ Error Boundaries use class components (still required)

**Optional Modernization:**
- React.FC typing still works but can be simplified later
- No immediate changes required

### 1.4 Verification Checklist

**Local Build:**
- [ ] `npx tsc --noEmit` - Zero TypeScript errors
- [ ] `npm run lint` - ESLint passes
- [ ] `npm test` - All tests pass
- [ ] `npm run dev` - Smoke test all routes
- [ ] `npm run build` - Production build succeeds

**Docker Build (CRITICAL):**
- [ ] `npm run docker:prod build` - Docker build succeeds
- [ ] Verify no Node/npm errors in build logs
- [ ] Check dist/ output created in builder stage
- [ ] Test container: `docker compose -f docker-compose.prod.yml up -d`
- [ ] Access http://localhost to verify frontend serves
- [ ] Check browser console for errors

**Manual Testing Routes:**
- [ ] /auth/login → GitHub OAuth flow
- [ ] / → Chat, Context, Ideas, Solve tabs
- [ ] User profile dropdown
- [ ] Repository selection

**Docker Compatibility Notes:**
- ✅ Node 18-alpine supports React 19 (requires Node ≥18.17.0)
- ✅ No Dockerfile changes needed
- ✅ Build process unchanged: npm ci → npm run build
- ✅ Static output served by nginx (version-agnostic)

---

## Phase 2: CLI-Inspired Design System (6-8 hours)

### 2.1 Font Loading (Required Foundation)

**File:** `index.html`

Add Google Fonts before closing `</head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

Already configured in Tailwind ✓

### 2.2 Terminal Scan-Line Texture

**File:** `src/index.css`

Add after existing utilities:
```css
@layer utilities {
  /* Authentic terminal scan lines */
  .scan-lines {
    position: relative;
  }

  .scan-lines::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.015) 0px,
      rgba(255, 255, 255, 0.015) 1px,
      transparent 1px,
      transparent 2px
    );
    z-index: 1;
  }

  /* CLI hover lift for buttons */
  .hover-lift {
    transition: transform 200ms cubic-bezier(0.25, 0.8, 0.25, 1),
                box-shadow 200ms cubic-bezier(0.25, 0.8, 0.25, 1);
  }

  .hover-lift:hover:not(:disabled) {
    transform: translateY(-2px);
  }
}
```

### 2.3 Terminal Cursor Blink

**File:** `tailwind.config.js`

Add to keyframes and animation:
```javascript
keyframes: {
  // ... existing
  cursorBlink: {
    '0%, 49%': { opacity: '1' },
    '50%, 100%': { opacity: '0' },
  },
},
animation: {
  // ... existing
  'cursor-blink': 'cursorBlink 1.2s steps(1, end) infinite',
},
```

### 2.4 CLI-Inspired Chat Enhancements

**File:** `src/components/Chat.tsx`

**Priority Changes:**
1. **Line 560:** Add scan-lines to container
   ```tsx
   className="h-full flex flex-col bg-bg terminal-noise scan-lines"
   ```

2. **Line 684:** Messages already have fade-in ✓ - enhance with:
   ```tsx
   // Add monospace for code/command feeling
   className="... font-mono"
   ```

3. **Lines 765, 779:** Add hover-lift to action buttons
   ```tsx
   className="... hover-lift"
   ```

4. **Message Role Labels:** Already has `Assistant`, `You`, `System` labels ✓

5. **Add CLI prompt indicator** to input area:
   ```tsx
   <div className="flex items-center gap-2">
     <span className="text-cyan font-mono">$</span>
     <input ... />
   </div>
   ```

### 2.5 Fix Hardcoded Colors (CRITICAL)

**Issue:** Components using `zinc-*` instead of design tokens breaks Terminal Precision consistency.

**Files to Fix:**

**`src/components/UserProfile.tsx`** (6 instances)
```tsx
// Replace all instances:
zinc-800/50  → bg-bg-tertiary
zinc-800     → bg-bg-secondary
zinc-700     → border-border
zinc-700/50  → bg-bg-tertiary
```

**`src/components/Sidebar.tsx`**
- Same pattern: zinc-* → design tokens
- Add `scan-lines` class to container
- Add `hover-lift` to tab buttons

**Also fix:** TrajectoryViewer.tsx, SessionErrorBoundary.tsx, AuthSuccess.tsx, AuthCallback.tsx

---

## Phase 3: CLI Micro-Interactions (3-4 hours)

### 3.1 LoginPage Terminal Enhancement

**File:** `src/components/LoginPage.tsx`

1. **Line 54:** Add scan-lines
   ```tsx
   className="... scan-lines"
   ```

2. **Line 86:** Add blinking cursor to hero
   ```tsx
   review-ready PRs.
   <span className="inline-block w-1 h-8 ml-1 bg-amber animate-cursor-blink" />
   ```

3. **Line 229:** Add hover-lift to GitHub button
   ```tsx
   className="w-full ... hover-lift"
   ```

### 3.2 TopBar CLI Enhancement

**File:** `src/components/TopBar.tsx`

Already well-implemented with:
- ✓ Gradient header
- ✓ Status indicators
- ✓ Glow on active tabs

Add subtle scan-lines for consistency.

### 3.3 Accessibility - Respect Motion Preferences

**File:** `src/index.css`

Add at bottom:
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Phase 4: Verification (2-3 hours)

### 4.1 Docker Production Build Verification

**CRITICAL: Test Docker build before deploying**

```bash
# Clean rebuild
docker compose -f docker-compose.prod.yml build --no-cache frontend

# Check build logs for errors
# Should see: "RUN npm run build" complete successfully

# Start production stack
docker compose -f docker-compose.prod.yml up -d

# Verify health
docker ps  # All containers should be "healthy"
curl http://localhost/health  # Should return "healthy"

# Test frontend
open http://localhost  # Should load without errors

# Check logs
docker logs yudai-fe  # No npm/build errors
```

**Expected Output:**
- ✓ Node 18 successfully installs React 19 dependencies
- ✓ Vite build completes without warnings
- ✓ dist/ directory created with all assets
- ✓ nginx serves application correctly
- ✓ No console errors in browser

**Troubleshooting:**
If build fails, check:
1. package-lock.json updated: `npm install` locally first
2. No peer dependency warnings
3. TypeScript compiles: `npx tsc --noEmit`

### 4.2 Visual Regression Testing

**Chat Interface (Primary Focus):**
- [ ] Scan-lines visible in message area
- [ ] CLI prompt `$` indicator shows
- [ ] Messages use monospace font
- [ ] Hover lift on Send/Create Issue buttons
- [ ] Role labels clear (Assistant/You/System)
- [ ] Smooth animations

**Login Page:**
- [ ] Cursor blinks on hero text
- [ ] Scan-lines visible on dark background
- [ ] JetBrains Mono loads in headlines
- [ ] Button hover lift works

**Overall:**
- [ ] All colors use design tokens (no zinc-*)
- [ ] Font loading works (Inter + JetBrains Mono)
- [ ] Terminal Precision aesthetic complete

### 4.3 Performance Check

**Local Build:**
```bash
npm run build
# Check dist/assets/js/ sizes vs baseline
```

**Docker Build:**
```bash
docker compose -f docker-compose.prod.yml build frontend
# Check build time vs baseline
```

Target: <10% bundle size increase
Target: Similar build time in Docker

### 4.4 Browser Testing
- Chrome/Edge (primary)
- Firefox
- Safari (if available)

### 4.5 Accessibility Audit
- Color contrast meets WCAG AA
- Keyboard navigation works
- Focus indicators visible
- Screen reader labels present

---

## Critical Files Priority Order

### Must Modify (Foundation):
1. `package.json` - React 19 dependencies
2. `index.html` - Google Fonts loading
3. `src/index.css` - scan-lines, hover-lift utilities
4. `tailwind.config.js` - cursor-blink animation

### High Priority (CLI Chat Experience):
5. `src/components/Chat.tsx` - CLI enhancements, hover-lift
6. `src/components/UserProfile.tsx` - Fix 6 zinc-* color instances
7. `src/components/Sidebar.tsx` - Design token migration

### Medium Priority (Visual Consistency):
8. `src/components/LoginPage.tsx` - Cursor blink, scan-lines
9. `src/components/TopBar.tsx` - Scan-lines
10. `src/components/TrajectoryViewer.tsx` - Color token migration

### Optional (If Time Permits):
11. `src/components/ContextCards.tsx` - Hover-lift
12. `src/components/SolveIssues.tsx` - Micro-interactions
13. `vite.config.ts` - Bundle analyzer

---

## Success Criteria

### React 19 Success:
- ✓ Zero TypeScript errors
- ✓ All tests pass
- ✓ No peer dependency warnings
- ✓ Production build succeeds
- ✓ No console errors in dev mode

### CLI Design Success:
- ✓ Chat feels like terminal interface
- ✓ Scan-line texture visible
- ✓ JetBrains Mono loads correctly
- ✓ Cursor blink animation works
- ✓ Hover lift on all buttons
- ✓ Zero zinc-* colors remaining
- ✓ 100% design-doc.md compliance

### Performance Success:
- ✓ Lighthouse score >90
- ✓ Bundle size increase <10%
- ✓ 60fps scrolling
- ✓ No FOIT (Flash of Invisible Text)

---

## Rollback Strategy

**Full Rollback:**
```bash
git checkout phase1-realtime
git branch -D upgrade/react-19-cli-design
npm install
```

**React Only Rollback:**
```bash
npm install react@18.3.1 react-dom@18.3.1
npm install -D @types/react@18.3.5 @types/react-dom@18.3.0
```

**CSS Only Rollback:**
```bash
git checkout phase1-realtime -- src/index.css tailwind.config.js
```

---

## CLI Design Principles (Frontend-Design Skill)

Following the frontend-design skill guidance:

**Bold Aesthetic Choices:**
- ✓ Terminal Precision theme (not generic)
- ✓ JetBrains Mono + Inter (distinctive fonts)
- ✓ Scan-line texture (authentic terminal feel)
- ✓ Amber/Cyan accents (warm + technical)
- ✓ Cursor blink (unexpected detail)

**Avoid AI Slop:**
- ✗ No generic Inter-only typography
- ✗ No purple gradients on white
- ✗ No cookie-cutter layouts
- ✓ Context-specific Terminal theme

**Micro-Interactions:**
- Hover lift (subtle elevation)
- Cursor blink (hero accent)
- Staggered fade-ins (messages)
- Pulse animations (status indicators)
- Glow effects (active states)

---

## Post-Implementation

### Documentation:
- Update README.md with React 19
- Document new utilities (.scan-lines, .hover-lift, .cursor-blink)
- Create design system guide

### Monitoring:
- Track bundle size trends
- Monitor Core Web Vitals
- Gather user feedback on CLI feel

### Future Enhancements:
- Command palette (⌘K) for CLI navigation
- Keyboard shortcuts for chat commands
- Syntax highlighting for code in messages
- Terminal-style autocomplete

---

## References

- [React 19 Release](https://react.dev/blog/2024/12/05/react-19)
- [React 19 Upgrade Guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide)
- Design Doc: `design-doc.md`
- Frontend Design Skill: `.claude/skills/frontend-design/SKILL.md`
