import { useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Github,
  GitPullRequestArrow,
  Loader2,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const CAPABILITIES = [
  { icon: Sparkles, label: 'Architect', value: 'Plan' },
  { icon: ShieldCheck, label: 'Tester', value: 'Verify' },
  { icon: TerminalSquare, label: 'Coder', value: 'Patch' },
  { icon: GitPullRequestArrow, label: 'GitHub', value: 'Ship' },
];

const STATS = [
  { label: 'Modes', value: '3' },
  { label: 'Runtime', value: 'Modal' },
  { label: 'Contract', value: 'OpenAPI' },
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
    <main className="relative min-h-dvh overflow-hidden bg-bg text-fg">
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(10,10,11,0.98),rgba(17,24,28,0.94)_48%,rgba(24,18,11,0.92))]" />
      <video
        aria-hidden="true"
        autoPlay
        className="absolute inset-0 h-full w-full object-cover opacity-16 mix-blend-screen image-outline"
        loop
        muted
        playsInline
        src="/videos/yudai-enterprise-intro.mp4"
      />

      <section className="relative mx-auto grid min-h-dvh w-full max-w-7xl content-center gap-10 px-5 py-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-center">
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex min-h-10 items-center gap-2 rounded-lg bg-cyan/10 px-3 text-sm font-medium text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.22)]">
            <Activity aria-hidden="true" className="size-4" />
            Agent framework console
          </div>

          <h1 className="text-balance text-5xl font-semibold tracking-normal text-fg sm:text-6xl lg:text-7xl">
            Yudai
          </h1>
          <p className="mt-5 max-w-2xl text-pretty text-lg leading-8 text-fg-secondary">
            A GitHub-native workspace for planning, testing, coding, and shipping repository changes through typed backend contracts.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-amber px-5 pl-5 pr-4 text-sm font-semibold text-black transition-[background-color,scale] duration-150 ease-out hover:bg-yellow-400 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100"
              disabled={isLoading}
              onClick={() => void handleLogin()}
              type="button"
            >
              {isLoading ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Github aria-hidden="true" className="size-4" />}
              Continue with GitHub
              <ArrowRight aria-hidden="true" className="size-4" />
            </button>
          </div>

          {visibleError && (
            <div className="mt-5 max-w-xl rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.26)]">
              {visibleError}
            </div>
          )}

          <div className="mt-10 grid max-w-xl grid-cols-3 gap-3">
            {STATS.map((stat) => (
              <div
                className="rounded-lg bg-bg-secondary/82 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
                key={stat.label}
              >
                <div className="tabular-nums text-2xl font-semibold text-fg">{stat.value}</div>
                <div className="mt-1 text-xs uppercase tracking-normal text-fg-muted">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg bg-bg-secondary/78 p-2 shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_24px_80px_rgba(0,0,0,0.35)]">
          <div className="rounded-md bg-bg-primary/88 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-balance text-base font-semibold">Pipeline</h2>
                <p className="text-xs text-fg-muted">Repository automation</p>
              </div>
              <Sparkles aria-hidden="true" className="size-5 text-amber" />
            </div>

            <div className="grid gap-2">
              {CAPABILITIES.map((capability, index) => {
                const Icon = capability.icon;

                return (
                  <div
                    className="grid min-h-16 grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg bg-bg-secondary px-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
                    key={capability.label}
                  >
                    <div className="grid size-10 place-items-center rounded-lg bg-cyan/10 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.16)]">
                      <Icon aria-hidden="true" className="size-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-fg">{capability.label}</div>
                      <div className="text-xs text-fg-muted">{capability.value}</div>
                    </div>
                    <span className="tabular-nums text-xs text-fg-muted">0{index + 1}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
