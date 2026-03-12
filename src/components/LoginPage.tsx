import { useMemo, useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const HERO_CHIPS = [
  'Governed Architect -> Tester -> Coder flow',
  'Audit-ready trajectory and artifact trail',
  'Org-scoped sandbox runtime controls',
];

const DELIVERY_STEPS = [
  {
    step: '01',
    title: 'Provision',
    description:
      'Select org, repo, and branch to initialize your controlled org + repo + environment runtime.',
    color: 'cyan',
  },
  {
    step: '02',
    title: 'Specify',
    description:
      'Architect mode converts requirements into scoped GitHub issues with acceptance criteria.',
    color: 'amber',
  },
  {
    step: '03',
    title: 'Assure',
    description:
      'Tester mode writes coverage-first unit, integration, and edge-case tests before coding.',
    color: 'emerald',
  },
  {
    step: '04',
    title: 'Deliver',
    description:
      'Coder mode implements, validates, and opens a PR while preserving traceable trajectory logs.',
    color: 'violet',
  },
];

const CAPABILITIES = [
  {
    title: 'Governed Multi-Mode Pipeline',
    description: 'Architect, Tester, and Coder execute with controlled handoffs.',
  },
  {
    title: 'Sandbox Identity Isolation',
    description: 'Runtime keyed by org + repo + environment.',
  },
  {
    title: 'Real-Time Operational Telemetry',
    description: 'WebSocket chat plus SSE trajectory streaming.',
  },
  {
    title: 'Issue-to-PR Lifecycle Gate',
    description: 'Execution completes only after issue and PR are created.',
  },
  {
    title: 'Audit Artifacts + Logs',
    description: 'Trace requirement, tests, implementation, and outcomes.',
  },
  {
    title: 'GitHub-Native Controls',
    description: 'Integrates with enterprise branch and review workflows.',
  },
];

const PANEL_BULLETS = [
  'Policy-aligned issue planning',
  'Coverage-first test generation',
  'Traceable PR delivery with audit logs',
];

const STEP_ACCENT_CLASSES: Record<string, string> = {
  cyan: 'bg-accent-cyan/10 border-accent-cyan/20 text-accent-cyan',
  amber: 'bg-accent-amber/10 border-accent-amber/20 text-accent-amber',
  emerald: 'bg-accent-emerald/10 border-accent-emerald/20 text-accent-emerald',
  violet: 'bg-accent-violet/10 border-accent-violet/20 text-accent-violet',
};

/**
 * LoginPage component handles GitHub OAuth login.
 * Auth handlers, URLs, and install flow are intentionally unchanged.
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
    <div className="min-h-screen bg-bg-primary text-text-primary selection:bg-accent-amber/30">
      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none opacity-[0.018]"
        style={{
          backgroundImage:
            'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")',
        }}
      />

      <section className="relative border-b border-border/80">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(17,217,146,0.18),transparent_32%),radial-gradient(circle_at_top_right,rgba(34,168,255,0.16),transparent_30%),linear-gradient(180deg,#061224_0%,#050b16_56%,#03060d_100%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent"
        />

        <div className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-16 pt-16 sm:pt-20 lg:grid-cols-12 lg:px-8 lg:pb-20 lg:pt-24">
          <div className="max-w-3xl lg:col-span-7">
            <img
              src="/branding/yudai-labs-lockup.svg"
              alt="Yudai Labs"
              className="h-14 w-auto sm:h-16"
            />

            <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-mono uppercase tracking-[0.2em] text-white/70">
              <span className="h-2 w-2 rounded-full bg-[#11D992]" />
              enterprise-ready delivery orchestration
            </div>

            <h1 className="max-w-4xl pb-2 pt-6 text-[clamp(2.9rem,6.2vw,5.7rem)] font-semibold leading-[0.98] tracking-[-0.04em] text-white">
              <span className="block">From requirement</span>
              <span className="block text-white/92">to issue, tests,</span>
              <span className="block bg-gradient-to-r from-[#11D992] via-[#22A8FF] to-[#F5F7FA] bg-clip-text text-transparent">
                and review-ready PRs.
              </span>
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/72 sm:text-xl">
              YudaiV3 connects to your GitHub stack and runs a governed
              Architect -&gt; Tester -&gt; Coder pipeline with full trajectory logs
              for audit and review confidence.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              {HERO_CHIPS.map((chip) => (
                <div
                  key={chip}
                  className="inline-flex min-h-11 items-center rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/78 backdrop-blur-sm"
                >
                  {chip}
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-5">
            <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(145deg,rgba(17,217,146,0.16),rgba(34,168,255,0.08),rgba(255,255,255,0.02))] p-[1px] shadow-[0_28px_90px_rgba(0,0,0,0.38)]">
              <div className="rounded-[27px] border border-white/6 bg-[#071122]/94 p-4 sm:p-5">
                <div className="mb-4 flex items-center justify-between rounded-2xl border border-white/8 bg-black/20 px-4 py-3">
                  <div>
                    <p className="text-xs font-mono uppercase tracking-[0.24em] text-white/50">
                      live delivery preview
                    </p>
                    <p className="mt-1 text-sm font-medium text-white/84">
                      issue planning, test generation, and PR opening
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-[#11D992]" />
                    <span className="h-2.5 w-2.5 rounded-full bg-[#22A8FF]" />
                    <span className="h-2.5 w-2.5 rounded-full bg-white/40" />
                  </div>
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/8 bg-[#030814]">
                  <video
                    className="aspect-video w-full object-cover"
                    src="/videos/yudai-enterprise-intro.mp4"
                    autoPlay
                    loop
                    muted
                    playsInline
                  />
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                    <p className="text-xs font-mono uppercase tracking-[0.2em] text-white/45">
                      governance
                    </p>
                    <p className="mt-2 text-sm leading-6 text-white/75">
                      Controlled issue-to-PR progression with linked GitHub work
                      at each stage.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                    <p className="text-xs font-mono uppercase tracking-[0.2em] text-white/45">
                      visibility
                    </p>
                    <p className="mt-2 text-sm leading-6 text-white/75">
                      Real-time trajectory, audit artifacts, and review context
                      built into the flow.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <main className="mx-auto grid max-w-6xl gap-12 px-6 py-16 lg:grid-cols-5 lg:gap-16 lg:px-8">
        <div className="space-y-10 lg:col-span-3">
          <section>
            <h2 className="mb-6 text-sm font-mono uppercase tracking-[0.24em] text-text-muted">
              How it works
            </h2>
            <div className="space-y-6">
              {DELIVERY_STEPS.map((item) => (
                <div key={item.step} className="flex gap-5">
                  <div className="flex-shrink-0">
                    <span
                      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border font-mono text-sm ${STEP_ACCENT_CLASSES[item.color]}`}
                    >
                      {item.step}
                    </span>
                  </div>
                  <div>
                    <h3 className="mb-1 text-lg font-medium text-text-primary">
                      {item.title}
                    </h3>
                    <p className="leading-relaxed text-text-secondary">
                      {item.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="border-t border-bg-tertiary pt-6">
            <h2 className="mb-6 text-sm font-mono uppercase tracking-[0.24em] text-text-muted">
              Capabilities
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {CAPABILITIES.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-2xl border border-bg-tertiary bg-bg-secondary p-5 transition-colors hover:border-border"
                >
                  <h3 className="mb-2 text-sm font-medium text-text-primary">
                    {feature.title}
                  </h3>
                  <p className="text-sm leading-6 text-text-muted">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="lg:col-span-2">
          <div className="lg:sticky lg:top-8">
            <div className="rounded-[26px] border border-white/10 bg-[linear-gradient(145deg,rgba(17,217,146,0.12),rgba(34,168,255,0.06),rgba(255,255,255,0.02))] p-[1px] shadow-[0_18px_70px_rgba(0,0,0,0.35)]">
              <div className="rounded-[25px] bg-bg-secondary/95 p-6 sm:p-8">
                <div className="mb-6">
                  <img
                    src="/branding/yudai-labs-lockup.svg"
                    alt="Yudai Labs"
                    className="mb-5 h-10 w-auto"
                  />
                  <h2 className="mb-2 text-2xl font-semibold text-text-primary">
                    Start an Enterprise Session
                  </h2>
                  <p className="text-sm leading-6 text-text-secondary">
                    Connect GitHub to run governed Architect -&gt; Tester -&gt;
                    Coder delivery workflows.
                  </p>
                </div>

                <div className="mb-6 rounded-2xl border border-accent-amber/12 bg-accent-amber/6 p-4">
                  <p className="mb-1 text-xs font-mono uppercase tracking-[0.22em] text-accent-amber/80">
                    enterprise onboarding
                  </p>
                  <p className="text-sm leading-6 text-text-secondary">
                    Authenticate with GitHub, then install the app to grant
                    secure repository access.
                  </p>
                </div>

                {errorMessage && (
                  <div className="mb-6 rounded-2xl border border-red-500/20 bg-red-500/10 p-4">
                    <p className="text-sm text-red-400">{errorMessage}</p>
                  </div>
                )}

                <div className="mb-6">
                  <div className="mb-3 flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-cyan-500/20 bg-cyan-500/10 text-xs font-mono text-cyan-400">
                      1
                    </span>
                    <span className="text-sm font-medium text-text-primary">
                      Sign in with GitHub
                    </span>
                  </div>

                  <button
                    onClick={handleGitHubLogin}
                    disabled={isLoading}
                    className="flex w-full items-center justify-center gap-3 rounded-xl bg-text-primary px-6 py-3.5 font-medium text-bg-primary transition-all duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-xl disabled:translate-y-0 disabled:bg-text-secondary"
                  >
                    {isLoading ? (
                      <>
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-bg-primary/20 border-t-bg-primary" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <>
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
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
                    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-amber-500/20 bg-amber-500/10 text-xs font-mono text-amber-400">
                      2
                    </span>
                    <span className="text-sm font-medium text-text-primary">
                      Install GitHub App
                    </span>
                  </div>

                  <a
                    href={githubAppInstallUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-border bg-bg-tertiary px-6 py-3 text-sm font-medium text-text-primary transition-colors hover:bg-bg-secondary"
                  >
                    Install GitHub App
                  </a>
                </div>

                <div className="mb-6 space-y-2.5 border-y border-bg-tertiary py-4">
                  {PANEL_BULLETS.map((item) => (
                    <div
                      key={item}
                      className="flex items-center gap-2.5 text-sm text-text-secondary"
                    >
                      <svg
                        className="h-4 w-4 flex-shrink-0 text-accent-emerald"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                <a
                  href="https://discord.gg/U96mwKmJ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-discord/20 bg-discord/10 px-6 py-3 font-medium text-text-primary transition-colors hover:bg-discord/20"
                >
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z" />
                  </svg>
                  <span>Join Engineering Community</span>
                </a>

                <div className="mt-6 border-t border-bg-tertiary pt-4">
                  <p className="text-center text-xs text-text-muted">
                    By signing in, you agree to our terms of service and
                    privacy policy
                  </p>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </main>

      <section className="border-t border-bg-tertiary">
        <div className="mx-auto max-w-4xl px-6 py-12 lg:px-8">
          <div className="text-center">
            <p className="mb-4 text-text-secondary">
              <span className="font-medium text-text-primary">
                Built for enterprise engineering teams
              </span>{' '}
              that need governed delivery, operational visibility, and reliable
              issue-to-PR execution.
            </p>
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-text-muted">
              <span className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-full bg-accent-cyan" />
                Org + repo + environment isolation
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-full bg-accent-amber" />
                Real-time operational telemetry
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-full bg-accent-emerald" />
                Issue + PR completion controls
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-1 w-1 rounded-full bg-accent-violet" />
                Auditable solver trajectories
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
