import { useMemo, useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const HERO_CHIPS = [
  'Governed Architect -> Tester -> Coder flow',
  'Audit-ready trajectory and artifact trail',
  'Org-scoped sandbox runtime controls',
] as const;

const HERO_PROOF_POINTS = [
  {
    label: 'Policy-aware execution',
    description: 'Turn requirements into scoped implementation work with deterministic handoffs.',
  },
  {
    label: 'Review confidence',
    description: 'Ship tests before code and keep every decision visible to reviewers.',
  },
  {
    label: 'GitHub-native control',
    description: 'Run inside the repo workflows your engineering team already trusts.',
  },
] as const;

const WORKFLOW_STEPS = [
  {
    step: '01',
    title: 'Provision',
    description: 'Select org, repo, and branch to initialize a controlled org + repo + environment runtime.',
    color: 'cyan',
  },
  {
    step: '02',
    title: 'Specify',
    description: 'Architect mode converts requirements into scoped GitHub issues with acceptance criteria.',
    color: 'blue',
  },
  {
    step: '03',
    title: 'Assure',
    description: 'Tester mode writes coverage-first unit, integration, and edge-case tests before coding.',
    color: 'emerald',
  },
  {
    step: '04',
    title: 'Deliver',
    description: 'Coder mode implements, validates, and opens a PR with a traceable execution trail.',
    color: 'slate',
  },
] as const;

const CAPABILITY_CARDS = [
  {
    title: 'Governed multi-mode pipeline',
    description: 'Architect, Tester, and Coder execute with explicit checkpoints and controlled handoffs.',
  },
  {
    title: 'Sandbox identity isolation',
    description: 'Runtime identity stays keyed by org + repo + environment for safer enterprise operations.',
  },
  {
    title: 'Real-time operational telemetry',
    description: 'Watch WebSocket and SSE updates as the delivery workflow moves from issue to PR.',
  },
  {
    title: 'Issue-to-PR lifecycle gating',
    description: 'Execution is only complete when planning, validation, and delivery are all accounted for.',
  },
  {
    title: 'Audit artifacts and logs',
    description: 'Trace the requirement, tests, implementation, and final review outputs in one place.',
  },
  {
    title: 'GitHub-native enterprise controls',
    description: 'Integrate with installation, review, and repository access patterns your team already uses.',
  },
] as const;

const AUTH_BULLETS = [
  'Policy-aligned issue planning',
  'Coverage-first test generation',
  'Traceable PR delivery with audit logs',
] as const;

const FOOTER_PILLARS = [
  'Org + repo + environment isolation',
  'Real-time operational telemetry',
  'Issue + PR completion controls',
  'Auditable solver trajectories',
] as const;

const STEP_ACCENT_CLASSES = {
  cyan: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-300',
  blue: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  emerald: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  slate: 'border-white/15 bg-white/5 text-white',
} as const;

const BrandLockup = () => (
  <div className="relative isolate aspect-[14/5] w-[240px] overflow-hidden rounded-[24px] border border-white/10 bg-[#051425] shadow-[0_24px_60px_rgba(0,0,0,0.35)] sm:w-[300px]">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(20,184,166,0.22),transparent_36%),radial-gradient(circle_at_80%_28%,rgba(14,165,233,0.18),transparent_32%)]" />
    <img
      src="/assets/baseLogo.png"
      alt="Yudai Labs"
      loading="eager"
      className="absolute left-1/2 top-1/2 w-[116%] max-w-none -translate-x-1/2 -translate-y-1/2"
    />
  </div>
);

/**
 * LoginPage component handles GitHub OAuth login
 * YudaiV3: Enterprise onboarding and delivery orchestration landing page
 */
export const LoginPage: React.FC = () => {
  const [error, setError] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    return errorParam ? decodeURIComponent(errorParam) : null;
  });
  const { login, isLoading, authError } = useAuth();

  const githubAppInstallUrl = useMemo(() => {
    const explicitUrl = import.meta.env.VITE_GITHUB_APP_INSTALL_URL;
    if (explicitUrl) {
      return explicitUrl;
    }

    const appSlug = import.meta.env.VITE_GITHUB_APP_SLUG;
    if (appSlug) {
      return `https://github.com/apps/${appSlug}/installations/new`;
    }

    return 'https://github.com/apps/yudaiv3';
  }, []);

  const handleGitHubLogin = async () => {
    try {
      setError(null);

      console.log('[LoginPage] Initiating GitHub OAuth login');

      await login();
    } catch (loginError) {
      console.error('[LoginPage] Login failed:', loginError);
      setError('Failed to initiate login. Please try again.');
    }
  };

  const errorMessage = error || authError;

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-bg-primary text-text-primary selection:bg-sky-400/20">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(5,12,24,0.92),rgba(10,10,11,0.96))]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.06] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:84px_84px]" />
      <div className="pointer-events-none absolute left-[-6rem] top-[12rem] h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[-7rem] top-16 h-80 w-80 rounded-full bg-emerald-400/10 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <section className="border-b border-white/10 pb-16 pt-8 sm:pb-20 sm:pt-10 lg:pb-24 lg:pt-14">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(360px,420px)] lg:items-start lg:gap-12">
            <div className="space-y-8">
              <div className="space-y-6">
                <BrandLockup />

                <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] text-text-secondary backdrop-blur-sm">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 motion-safe:animate-pulse motion-reduce:animate-none" />
                  enterprise-ready delivery orchestration
                </div>

                <div className="space-y-5">
                  <h1 className="max-w-4xl pb-2 text-[clamp(3rem,7vw,5.75rem)] font-semibold leading-[1.04] tracking-[-0.055em] text-white">
                    From requirement to issue, tests, and{' '}
                    <span className="bg-gradient-to-r from-emerald-300 via-cyan-300 to-sky-400 bg-clip-text text-transparent">
                      review-ready PRs.
                    </span>
                  </h1>

                  <p className="max-w-3xl text-lg leading-8 text-text-secondary sm:text-xl">
                    {'YudaiV3 connects to your GitHub stack and runs a governed Architect -> Tester -> Coder '}
                    pipeline with full trajectory logs for auditability, visibility, and review confidence.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                {HERO_CHIPS.map((chip) => (
                  <div
                    key={chip}
                    className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-text-secondary backdrop-blur-sm"
                  >
                    {chip}
                  </div>
                ))}
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {HERO_PROOF_POINTS.map((point) => (
                  <div
                    key={point.label}
                    className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-[0_18px_40px_rgba(0,0,0,0.22)] backdrop-blur-sm"
                  >
                    <p className="text-sm font-semibold text-white">{point.label}</p>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">{point.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-6 lg:sticky lg:top-8">
              <div className="rounded-[30px] border border-white/10 bg-[linear-gradient(180deg,rgba(9,19,35,0.92),rgba(6,10,19,0.88))] p-3 shadow-[0_30px_80px_rgba(0,0,0,0.38)]">
                <div className="rounded-[24px] border border-white/10 bg-[#08111d]/90 p-4 backdrop-blur-sm">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.24em] text-text-muted">
                      <span className="h-2 w-2 rounded-full bg-cyan-300 motion-safe:animate-pulse motion-reduce:animate-none" />
                      Live workflow preview
                    </div>
                    <span className="text-[11px] font-medium uppercase tracking-[0.24em] text-text-muted">
                      review confidence
                    </span>
                  </div>

                  <div className="overflow-hidden rounded-[20px] border border-white/10 bg-black">
                    <video
                      autoPlay
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      aria-label="Enterprise delivery workflow preview video"
                      className="aspect-[16/10] w-full object-cover"
                    >
                      <source src="/videos/yudai-enterprise-intro.mp4" type="video/mp4" />
                    </video>
                  </div>

                  <p className="mt-4 text-sm leading-6 text-text-secondary">
                    Watch issue planning, test generation, and PR delivery with live trajectory visibility
                    before you connect GitHub.
                  </p>
                </div>
              </div>

              <div className="rounded-[30px] border border-white/10 bg-white/[0.04] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.32)] backdrop-blur-md sm:p-8">
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.24em] text-text-muted">
                      Enterprise onboarding
                    </p>
                    <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-white">
                      Start an Enterprise Session
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      {'Connect GitHub to run governed Architect -> Tester -> Coder delivery workflows.'}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-right">
                    <p className="text-[10px] uppercase tracking-[0.24em] text-text-muted">Access</p>
                    <p className="mt-1 text-sm font-medium text-white">OAuth + App install</p>
                  </div>
                </div>

                <div className="mb-6 rounded-[22px] border border-cyan-400/15 bg-cyan-400/5 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-200/80">
                    Two-step secure setup
                  </p>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">
                    Authenticate with GitHub, then install the app to grant secure repository access.
                  </p>
                </div>

                {errorMessage && (
                  <div
                    role="alert"
                    className="mb-6 rounded-[20px] border border-red-500/25 bg-red-500/10 p-4"
                  >
                    <p className="text-sm text-red-300">{errorMessage}</p>
                  </div>
                )}

                <div className="mb-6">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-400/10 text-xs font-mono text-cyan-300">
                      1
                    </span>
                    <span className="text-sm font-medium text-white">Sign in with GitHub</span>
                  </div>

                  <button
                    onClick={handleGitHubLogin}
                    disabled={isLoading}
                    className="flex w-full cursor-pointer items-center justify-center gap-3 rounded-2xl bg-white px-6 py-4 text-sm font-semibold text-slate-950 transition-all duration-200 hover:-translate-y-0.5 hover:bg-slate-100 disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-500 disabled:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
                  >
                    {isLoading ? (
                      <>
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-950/20 border-t-slate-950" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <>
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                          <path
                            fillRule="evenodd"
                            d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                        <span>Sign in with GitHub</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="mb-6">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-emerald-400/20 bg-emerald-400/10 text-xs font-mono text-emerald-300">
                      2
                    </span>
                    <span className="text-sm font-medium text-white">Install GitHub App</span>
                  </div>

                  <a
                    href={githubAppInstallUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex w-full cursor-pointer items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] px-6 py-4 text-sm font-semibold text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
                  >
                    Install GitHub App
                  </a>
                </div>

                <div className="mb-6 space-y-3 rounded-[22px] border border-white/10 bg-[#08111d]/80 px-4 py-5">
                  {AUTH_BULLETS.map((item) => (
                    <div key={item} className="flex items-center gap-3 text-sm text-text-secondary">
                      <svg
                        className="h-4 w-4 flex-shrink-0 text-emerald-300"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                        aria-hidden="true"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                <a
                  href="https://discord.gg/U96mwKmJ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-full cursor-pointer items-center justify-center gap-2.5 rounded-2xl border border-discord/20 bg-discord/10 px-6 py-4 text-sm font-semibold text-white transition-colors duration-200 hover:bg-discord/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-discord focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary"
                >
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z" />
                  </svg>
                  <span>Join Engineering Community</span>
                </a>

                <div className="mt-6 border-t border-white/10 pt-4">
                  <p className="text-center text-xs leading-5 text-text-muted">
                    By signing in, you agree to our terms of service and privacy policy.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-6 py-16 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:py-20">
          <div className="rounded-[32px] border border-white/10 bg-white/[0.03] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur-sm sm:p-8">
            <div className="mb-8">
              <p className="text-xs font-medium uppercase tracking-[0.24em] text-text-muted">How it works</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white">
                A controlled path from specification to merged work
              </h2>
            </div>

            <div className="space-y-5">
              {WORKFLOW_STEPS.map((item) => (
                <div
                  key={item.step}
                  className="flex gap-4 rounded-[24px] border border-white/10 bg-[#08111d]/80 p-4 sm:gap-5 sm:p-5"
                >
                  <div className="flex-shrink-0">
                    <span
                      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl border text-sm font-mono ${STEP_ACCENT_CLASSES[item.color]}`}
                    >
                      {item.step}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">{item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[32px] border border-white/10 bg-white/[0.03] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur-sm sm:p-8">
            <div className="mb-8">
              <p className="text-xs font-medium uppercase tracking-[0.24em] text-text-muted">Capabilities</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-white">
                Enterprise controls without losing delivery speed
              </h2>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {CAPABILITY_CARDS.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-[24px] border border-white/10 bg-[#08111d]/80 p-5 transition-colors duration-200 hover:border-cyan-300/20"
                >
                  <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-white">
                    {feature.title}
                  </h3>
                  <p className="mt-3 text-sm leading-6 text-text-secondary">{feature.description}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 rounded-[24px] border border-emerald-400/15 bg-emerald-400/5 p-5">
              <p className="text-sm font-semibold text-white">
                Built for engineering teams that need governance, visibility, and review confidence in one loop.
              </p>
            </div>
          </div>
        </section>
      </div>

      <div className="border-t border-white/10 bg-black/10">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-sm text-text-muted">
            {FOOTER_PILLARS.map((item) => (
              <span key={item} className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
