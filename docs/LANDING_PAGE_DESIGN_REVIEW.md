# Landing Page Design Review

## Reference Observations

The Godel Machines reference at `https://godelmachines.io` uses a sticky top toolbar, a centered announcement pill, a first-screen hero, serif italic display type, mono uppercase navigation, a right-side terminal surface, dotted vertical rules, warm near-black surfaces, cream text, taupe secondary copy, orange accents, and subtle grain.

Yudai Labs adapts the structure without copying assets, copy, marks, or product claims. The public page now speaks to governed GitHub delivery rather than self-evolving models: repository context, explicit stages, tests, PRs, traceability, and backend-owned runtime control.

## Palette

- Background: warm near-black for the public page only, scoped under `.yudai-landing`.
- Text: cream primary text with taupe secondary text for softer technical copy.
- Accent: orange for primary CTAs, announcement state, and terminal emphasis.
- Status: green appears only for successful evidence or lifecycle state.
- Rules: low-opacity cream borders and dotted vertical grid rules.

The authenticated app can continue using its existing global Tailwind variables. The landing page owns its warmer palette through scoped CSS custom properties in `src/index.css`.

## Typography

- Brand and hero display use an italic serif stack to create the editorial public-page moment.
- Navigation, buttons, terminal preview, cards, and operational copy use the mono stack to keep the page engineering-focused.
- Letter spacing stays at the browser default so labels remain readable and consistent with the app rules.
- Hero sizes change through breakpoints, not viewport-width font scaling.

## Layout

- Sticky toolbar with brand, primary anchors, and GitHub sign-in.
- Centered preview announcement above the hero.
- First-screen hero with large logo, Yudai Labs wordmark, primary GitHub CTA, proof points, and a desktop terminal panel.
- Anchor sections for Product, Workflow, Security, Docs, and Get Started.
- Product/workflow media uses the real `yudai-enterprise-intro.mp4` in a contained video frame with controls. It is not used as a blurred background texture.

## Brand Voice

The page should sound concise, confident, and engineering-led. Prefer concrete nouns: repository context, tests, runtime, artifacts, PRs, audit events, bearer session, Modal sandbox. Avoid vague enterprise hype, model grandiosity, and claims that imply autonomous production changes without review.

## Accessibility

- Primary nav uses named links that target real section IDs.
- GitHub CTAs are buttons with visible labels and disabled loading state.
- Route, auth-store, and local login errors render in a `role="alert"` region.
- Decorative header logos use empty alt text; the hero logo has `alt="Yudai Labs logo"`.
- The workflow video has controls and an accessible label.
- Focus outlines remain globally visible through `src/index.css`.

## QA Checklist

- `npm run test:auth` passes.
- `npm run build` passes.
- Header anchors scroll to Product, Workflow, Security, Docs, and Get Started.
- Desktop views show the right-side terminal panel and contained workflow video.
- Mobile views do not overlap text, cards, buttons, or media.
- The logo and video assets load from `/assets/baseLogo.png` and `/videos/yudai-enterprise-intro.mp4`.
- The landing page keeps `useAuth().login()`, loading state, route errors, auth-store errors, and local login failures intact.
