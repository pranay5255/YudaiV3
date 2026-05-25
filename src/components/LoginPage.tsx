import { useMemo, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Code2,
  Github,
  GitPullRequestArrow,
  Loader2,
  PanelsTopLeft,
  Play,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const ENTERPRISE_VIDEO_SRC = '/videos/yudai-enterprise-intro.mp4';
const BRAND_LOGO_SRC = '/assets/baseLogo.png';

const NAV_LINKS = [
  { href: '#product', label: 'Product' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#security', label: 'Security' },
  { href: '#docs', label: 'Docs' },
  { href: '#get-started', label: 'Get Started' },
];

const HERO_PROOF = [
  { label: 'Mode order', value: 'A/T/C' },
  { label: 'Delivery target', value: 'GitHub' },
  { label: 'Runtime owner', value: 'Backend' },
];

const TERMINAL_LINES = [
  { label: 'repo', value: 'connected with branch and issue context' },
  { label: 'architect', value: 'constraints mapped before execution' },
  { label: 'tester', value: 'contracts and checks captured as evidence' },
  { label: 'coder', value: 'patch prepared for reviewable PR flow' },
];

const PRODUCT_POINTS = [
  {
    copy: 'Repository, branch, issue, and prior session context stay attached to the run from prompt to PR.',
    icon: PanelsTopLeft,
    title: 'Repo context first',
  },
  {
    copy: 'Architect, Tester, and Coder stages are explicit product states, not hidden prompt choreography.',
    icon: Code2,
    title: 'Governed execution',
  },
  {
    copy: 'Every run keeps artifacts, decisions, questions, and GitHub outcomes traceable for review.',
    icon: GitPullRequestArrow,
    title: 'Reviewable output',
  },
];

const WORKFLOW_STEPS = [
  {
    copy: 'Define the repo, branch, objective, constraints, and any human questions before the runtime moves.',
    icon: PanelsTopLeft,
    title: 'Architect',
  },
  {
    copy: 'Run contract-aware checks and capture the evidence reviewers need before implementation starts.',
    icon: ShieldCheck,
    title: 'Tester',
  },
  {
    copy: 'Apply scoped edits inside the sandbox and prepare the change for GitHub-native delivery.',
    icon: Code2,
    title: 'Coder',
  },
  {
    copy: 'Publish issues or PRs with session context, artifacts, and the audit trail still attached.',
    icon: GitPullRequestArrow,
    title: 'PR handoff',
  },
];

const SECURITY_POINTS = [
  'GitHub OAuth and bearer-session auth remain backend owned.',
  'The browser never executes shell commands directly against Modal.',
  'Runtime profiles and published versions define what agents can use.',
  'Audit events preserve questions, artifacts, mode state, and delivery links.',
];

const DOC_ITEMS = [
  {
    body: 'Routes, auth, AI stream, and backend ownership boundaries live in the architecture guide.',
    title: 'Architecture map',
  },
  {
    body: 'Mode order, runtime profile versions, and sandbox lifecycle rules are documented as contracts.',
    title: 'Runtime contracts',
  },
  {
    body: 'The landing-page design review captures palette, typography, layout, accessibility, and QA rules.',
    title: 'Design review',
  },
];

function getAuthError(): string | null {
  const searchParams = new URLSearchParams(window.location.search);
  const error = searchParams.get('error');

  if (!error) {
    return null;
  }

  return error.replace(/_/g, ' ');
}

export function LoginPage(): JSX.Element {
  const { authError, isLoading, login } = useAuth();
  const [localError, setLocalError] = useState<string | null>(null);
  const routeError = useMemo(getAuthError, []);
  const visibleError = localError || authError || routeError;

  async function handleLogin(): Promise<void> {
    setLocalError(null);

    try {
      await login();
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : 'Login failed');
    }
  }

  return (
    <div className="yudai-landing">
      <div aria-hidden="true" className="yudai-rules">
        <span />
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>

      <header className="yudai-nav">
        <a aria-label="Yudai Labs home" className="yudai-nav-brand" href="#top">
          <span className="yudai-nav-mark" aria-hidden="true">
            <img alt="" src={BRAND_LOGO_SRC} />
          </span>
          <span className="yudai-nav-wordmark">Yudai Labs</span>
        </a>

        <nav aria-label="Primary" className="yudai-nav-links">
          {NAV_LINKS.map((link) => (
            <a href={link.href} key={link.href}>{link.label}</a>
          ))}
        </nav>

        <button
          aria-label="Sign in with GitHub"
          className="yudai-nav-signin"
          disabled={isLoading}
          onClick={() => void handleLogin()}
          type="button"
        >
          <Github aria-hidden="true" />
          <span>Sign in</span>
        </button>
      </header>

      <main id="top">
        <a className="yudai-announcement" href="#workflow">
          <span className="yudai-announcement__label">Preview</span>
          <span>Governed GitHub delivery with Architect, Tester, and Coder stages.</span>
          <ArrowRight aria-hidden="true" />
        </a>

        <section aria-labelledby="yudai-hero-title" className="yudai-hero">
          <div className="yudai-hero-copy">
            <div className="yudai-hero-logo">
              <img
                alt="Yudai Labs logo"
                className="yudai-hero-logo__mark"
                src={BRAND_LOGO_SRC}
              />
              <p>Repo-governed agents</p>
            </div>

            <h1 className="yudai-hero-title" id="yudai-hero-title">
              <span>Yudai Labs</span>
              <em>governed agent delivery for GitHub repositories.</em>
            </h1>

            <p className="yudai-hero-subtitle">
              Yudai turns repository context, tests, sandbox execution, and PR handoff into one traceable workflow. Engineers keep review authority while agents work inside explicit product boundaries.
            </p>

            <div className="yudai-hero-actions">
              <button
                className="yudai-button yudai-button--primary"
                disabled={isLoading}
                onClick={() => void handleLogin()}
                type="button"
              >
                {isLoading ? <Loader2 aria-hidden="true" className="yudai-spin" /> : <Github aria-hidden="true" />}
                <span>{isLoading ? 'Opening GitHub...' : 'Continue with GitHub'}</span>
                <ArrowRight aria-hidden="true" />
              </button>
              <a className="yudai-button yudai-button--ghost" href="#product">
                <span>See product</span>
              </a>
            </div>

            {visibleError && (
              <div className="yudai-auth-error" role="alert">
                {visibleError}
              </div>
            )}

            <div className="yudai-proof-grid" aria-label="Yudai delivery facts">
              {HERO_PROOF.map((item) => (
                <div className="yudai-proof" key={item.label}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>

          <aside className="yudai-agent-panel" aria-label="Yudai agent lifecycle terminal preview">
            <div className="yudai-terminal-bar">
              <span />
              <span />
              <span />
              <strong>yudai-agent</strong>
            </div>
            <div className="yudai-terminal-body">
              <p className="yudai-terminal-command">$ yudai run --repo selected --mode governed</p>
              {TERMINAL_LINES.map((line) => (
                <div className="yudai-terminal-line" key={line.label}>
                  <span>{line.label}</span>
                  <p>{line.value}</p>
                </div>
              ))}
              <div className="yudai-terminal-status">
                <CheckCircle2 aria-hidden="true" />
                <span>Evidence ready for reviewer handoff</span>
              </div>
            </div>
          </aside>
        </section>

        <section className="yudai-section yudai-product" id="product">
          <div className="yudai-section-copy">
            <p className="yudai-kicker">Product</p>
            <h2>Agent work that stays inside the repo contract.</h2>
            <p>
              The landing page is public, but the promise is operational: connect GitHub, choose the repository, run a governed lifecycle, and keep the result attached to evidence your team can review.
            </p>
          </div>

          <div className="yudai-feature-grid">
            {PRODUCT_POINTS.map((point) => {
              const Icon = point.icon;

              return (
                <article className="yudai-feature-card" key={point.title}>
                  <Icon aria-hidden="true" />
                  <h3>{point.title}</h3>
                  <p>{point.copy}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="yudai-section yudai-workflow" id="workflow">
          <div className="yudai-workflow-copy">
            <p className="yudai-kicker">Workflow</p>
            <h2>From objective to PR, with each stage visible.</h2>
            <ol className="yudai-workflow-list">
              {WORKFLOW_STEPS.map((step) => {
                const Icon = step.icon;

                return (
                  <li key={step.title}>
                    <Icon aria-hidden="true" />
                    <div>
                      <h3>{step.title}</h3>
                      <p>{step.copy}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>

          <div className="yudai-video-frame">
            <div className="yudai-video-toolbar">
              <span>Enterprise workflow</span>
              <Play aria-hidden="true" />
            </div>
            <video
              aria-label="Yudai enterprise workflow demo video"
              className="yudai-workflow-video"
              controls
              muted
              playsInline
              preload="metadata"
              src={ENTERPRISE_VIDEO_SRC}
            />
          </div>
        </section>

        <section className="yudai-section yudai-security" id="security">
          <div className="yudai-section-copy">
            <p className="yudai-kicker">Security</p>
            <h2>Control plane first, sandbox second.</h2>
            <p>
              Yudai keeps authentication, repository access, execution state, and artifact ownership in the backend. The frontend presents state; it does not become the runtime authority.
            </p>
          </div>

          <div className="yudai-security-grid">
            {SECURITY_POINTS.map((point) => (
              <article className="yudai-security-card" key={point}>
                <ShieldCheck aria-hidden="true" />
                <p>{point}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="yudai-section yudai-docs" id="docs">
          <div className="yudai-section-copy">
            <p className="yudai-kicker">Docs</p>
            <h2>Implementation rules are documented with the product surface.</h2>
            <p>
              The public page mirrors the same principles used in the app: concise copy, clear ownership boundaries, visible state, and traceability over hype.
            </p>
          </div>

          <div className="yudai-doc-grid">
            {DOC_ITEMS.map((item) => (
              <article className="yudai-doc-card" key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="yudai-get-started" id="get-started">
          <div>
            <p className="yudai-kicker">Get Started</p>
            <h2>Bring the workflow into your GitHub session.</h2>
            <p>
              Sign in with GitHub to enter the authenticated Agent Workbench, select a repository, and start a governed run.
            </p>
          </div>
          <button
            className="yudai-button yudai-button--primary"
            disabled={isLoading}
            onClick={() => void handleLogin()}
            type="button"
          >
            {isLoading ? <Loader2 aria-hidden="true" className="yudai-spin" /> : <Github aria-hidden="true" />}
            <span>{isLoading ? 'Opening GitHub...' : 'Start with GitHub'}</span>
            <ArrowRight aria-hidden="true" />
          </button>
        </section>
      </main>

      <footer className="yudai-footer">
        <a className="yudai-nav-brand" href="#top">
          <span className="yudai-nav-mark" aria-hidden="true">
            <img alt="" src={BRAND_LOGO_SRC} />
          </span>
          <span className="yudai-nav-wordmark">Yudai Labs</span>
        </a>
        <span>GitHub-native agent delivery with traceable execution.</span>
      </footer>
    </div>
  );
}
