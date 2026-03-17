import { useMemo, useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const workflowSteps = [
  {
    label: '01/auth',
    title: 'Authenticate operator',
    description: 'GitHub OAuth confirms the account that will start the session.',
  },
  {
    label: '02/install',
    title: 'Grant repository access',
    description: 'Install the GitHub App on the org or repo that YudaiV3 should operate on.',
  },
  {
    label: '03/run',
    title: 'Ship with traceability',
    description: 'Requirements, tests, code, and PR output stay tied to one auditable run.',
  },
] as const;

const operatorNotes = [
  'issue -> tests -> implementation -> pr',
  'repo-scoped runtime controls',
  'trajectory logs retained for review',
] as const;

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
      <div className="fixed inset-0 pointer-events-none opacity-40 terminal-noise" />

      <main className="relative mx-auto flex min-h-screen max-w-5xl items-center px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
        <section className="w-full overflow-hidden rounded-2xl border border-border bg-bg-secondary/95 shadow-terminal backdrop-blur-sm">
          <div className="flex items-center justify-between gap-4 border-b border-border px-4 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted sm:px-6">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-accent-amber/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-accent-cyan/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-accent-emerald/80" />
            </div>
            <span className="truncate">yudai://auth/login</span>
            <span className="hidden sm:inline">secure bootstrap</span>
          </div>

          <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
            <div className="border-b border-border p-5 sm:p-8 lg:border-b-0 lg:border-r">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-accent-cyan">
                governed delivery runtime
              </p>

              <h1 className="mt-4 max-w-2xl font-mono text-3xl font-semibold leading-tight sm:text-4xl">
                review-ready GitHub delivery,
                <br />
                without the UI noise
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-7 text-text-secondary sm:text-base">
                Connect GitHub once. YudaiV3 turns requirements into issues, tests, implementation,
                and review-ready pull requests with a full audit trail.
              </p>

              <div className="mt-8 space-y-3">
                {workflowSteps.map((step) => (
                  <div
                    key={step.label}
                    className="rounded-xl border border-border bg-bg-primary/60 px-4 py-4"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          {step.label}
                        </p>
                        <h2 className="mt-1 font-mono text-sm font-semibold text-text-primary sm:text-base">
                          {step.title}
                        </h2>
                      </div>
                      <span className="w-fit rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-text-muted">
                        online
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-text-secondary">{step.description}</p>
                  </div>
                ))}
              </div>

              <div className="mt-8 rounded-xl border border-border bg-bg-primary/70 p-4">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent-amber">
                  operator notes
                </p>
                <div className="mt-3 space-y-2 font-mono text-sm text-text-secondary">
                  {operatorNotes.map((note) => (
                    <div key={note} className="flex items-start gap-3">
                      <span className="text-accent-amber">$</span>
                      <span>{note}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <aside className="p-5 sm:p-8">
              <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-accent-amber">
                access control
              </p>
              <h2 className="mt-4 font-mono text-xl font-semibold text-text-primary">
                initialize session
              </h2>
              <p className="mt-3 text-sm leading-6 text-text-secondary">
                Two steps: authenticate the GitHub user, then install the app on the target repo or
                organization.
              </p>

              {errorMessage && (
                <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                  <p className="font-mono text-xs uppercase tracking-[0.16em] text-red-300">
                    auth_error
                  </p>
                  <p className="mt-2 text-sm text-red-200">{errorMessage}</p>
                </div>
              )}

              <div className="mt-6 space-y-4">
                <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent-cyan">
                        step_01
                      </p>
                      <h3 className="mt-1 font-mono text-sm font-semibold text-text-primary">
                        sign in with github
                      </h3>
                    </div>
                    <span className="rounded-md border border-accent-cyan/20 bg-accent-cyan/10 px-2 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-accent-cyan">
                      required
                    </span>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-text-secondary">
                    Start a governed session for your GitHub identity.
                  </p>

                  <button
                    type="button"
                    onClick={handleGitHubLogin}
                    disabled={isLoading}
                    className="mt-4 flex w-full items-center justify-between rounded-lg border border-accent-cyan/30 bg-bg-secondary px-4 py-3 font-mono text-sm font-semibold text-text-primary transition-colors hover:border-accent-cyan/50 hover:bg-bg-primary disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span>{isLoading ? 'authorizing...' : 'sign_in_with_github'}</span>
                    <span className="text-accent-cyan">{isLoading ? '...' : '->'}</span>
                  </button>
                </div>

                <div className="rounded-xl border border-border bg-bg-primary/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted">
                        step_02
                      </p>
                      <h3 className="mt-1 font-mono text-sm font-semibold text-text-primary">
                        install github app
                      </h3>
                    </div>
                    <span className="rounded-md border border-border bg-bg-secondary px-2 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-text-muted">
                      next
                    </span>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-text-secondary">
                    Grant repository access so YudaiV3 can create issues, tests, and pull requests.
                  </p>

                  <a
                    href={githubAppInstallUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 flex w-full items-center justify-between rounded-lg border border-border bg-bg-secondary px-4 py-3 font-mono text-sm font-semibold text-text-primary transition-colors hover:border-border-accent hover:bg-bg-primary"
                  >
                    <span>open_install_page</span>
                    <span className="text-accent-amber">{'->'}</span>
                  </a>
                </div>
              </div>

              <div className="mt-6 rounded-xl border border-border bg-bg-primary/70 p-4 font-mono text-xs text-text-muted">
                <div className="flex items-center justify-between gap-4 border-b border-border pb-3">
                  <span>session_mode</span>
                  <span className="text-accent-emerald">governed</span>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-border py-3">
                  <span>artifact_trail</span>
                  <span className="text-accent-cyan">enabled</span>
                </div>
                <div className="flex items-center justify-between gap-4 pt-3">
                  <span>community</span>
                  <a
                    href="https://discord.gg/U96mwKmJ"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent-amber transition-colors hover:text-text-primary"
                  >
                    discord
                  </a>
                </div>
              </div>

              <p className="mt-6 text-center text-xs text-text-muted">
                By signing in, you agree to the service terms and privacy policy.
              </p>
            </aside>
          </div>
        </section>
      </main>
    </div>
  );
};
