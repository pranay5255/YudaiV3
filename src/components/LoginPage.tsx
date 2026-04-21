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
    <main className="relative isolate min-h-dvh overflow-x-hidden bg-bg text-fg">
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(135deg,rgba(10,10,11,0.98),rgba(17,24,28,0.96)_52%,rgba(24,18,11,0.94))]" />
      <video
        aria-hidden="true"
        autoPlay
        className="pointer-events-none absolute inset-y-0 right-0 z-0 hidden h-full w-[58%] object-cover opacity-[0.06] blur-[2px] brightness-[0.46] saturate-[0.7] lg:block"
        loop
        muted
        playsInline
        preload="metadata"
        src="/videos/yudai-enterprise-intro.mp4"
      />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_78%_40%,rgba(245,158,11,0.14),transparent_34%),linear-gradient(90deg,rgba(10,10,11,0.92),rgba(10,10,11,0.64)_54%,rgba(10,10,11,0.9))]" />

      <section className="relative z-10 mx-auto grid min-h-dvh w-full max-w-7xl grid-cols-[minmax(0,1fr)] content-start gap-8 px-5 py-8 sm:px-8 sm:py-12 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)] lg:content-center lg:items-center lg:gap-12">
        <div className="w-full min-w-0 max-w-3xl">
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
              className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-amber px-5 pl-5 pr-4 text-sm font-semibold text-black transition-[background-color,scale] duration-150 ease-out hover:bg-yellow-400 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 sm:w-auto"
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

          <div className="mt-10 grid w-full max-w-xl grid-cols-[repeat(3,minmax(0,1fr))] gap-2 sm:gap-3">
            {STATS.map((stat) => (
              <div
                className="min-w-0 rounded-lg bg-bg-secondary/82 p-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] sm:p-4"
                key={stat.label}
              >
                <div className="truncate text-base font-semibold tabular-nums text-fg sm:text-2xl">{stat.value}</div>
                <div className="mt-1 truncate text-xs uppercase tracking-normal text-fg-muted">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        <aside className="w-full min-w-0 rounded-lg bg-bg-secondary/84 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_24px_80px_rgba(0,0,0,0.35)] sm:p-5">
          <div className="mb-4 flex min-w-0 items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-balance text-base font-semibold">Pipeline</h2>
              <p className="truncate text-xs text-fg-muted">Repository automation</p>
            </div>
            <Sparkles aria-hidden="true" className="size-5 shrink-0 text-amber" />
          </div>

          <div className="grid gap-2">
            {CAPABILITIES.map((capability, index) => {
              const Icon = capability.icon;

              return (
                <div
                  className="grid min-h-16 min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-lg bg-bg-tertiary/82 px-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
                  key={capability.label}
                >
                  <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-cyan/10 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.16)]">
                    <Icon aria-hidden="true" className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-fg">{capability.label}</div>
                    <div className="truncate text-xs text-fg-muted">{capability.value}</div>
                  </div>
                  <span className="text-xs tabular-nums text-fg-muted">0{index + 1}</span>
                </div>
              );
            })}
          </div>
        </aside>
      </section>
    </main>
  );
}
