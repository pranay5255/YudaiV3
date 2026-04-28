import { useMemo, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Code2,
  FlaskConical,
  Github,
  GitPullRequestArrow,
  Loader2,
  Network,
  PlayCircle,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const MODE_OVERVIEWS = [
  {
    description: 'Turns a selected GitHub issue into a scoped implementation brief with affected systems, risks, and PR boundaries.',
    icon: Network,
    label: 'Architect',
    value: 'Plan',
  },
  {
    description: 'Builds test evidence, validates fixtures, and records the branch or checks the Coder should rely on.',
    icon: FlaskConical,
    label: 'Tester',
    value: 'Verify',
  },
  {
    description: 'Applies the patch in the repository, runs validation, and returns PR metadata that reviewers can inspect.',
    icon: Code2,
    label: 'Coder',
    value: 'Patch',
  },
];

const PRODUCT_POINTS = [
  'Issue-guided PR creation',
  'Modal-backed repository runtime',
  'OpenAPI-typed frontend contracts',
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
    <main className="relative isolate min-h-dvh overflow-hidden bg-bg text-fg">
      <video
        aria-hidden="true"
        autoPlay
        className="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover opacity-30"
        loop
        muted
        playsInline
        poster="/assets/baseLogo.png"
        preload="metadata"
      >
        <source src="/videos/yudai-enterprise-intro.mp4" type="video/mp4" />
      </video>
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(180deg,rgba(5,12,24,0.88),rgba(10,10,11,0.94)_54%,rgba(10,10,11,1)),linear-gradient(90deg,rgba(10,10,11,0.98),rgba(10,10,11,0.74)_48%,rgba(10,10,11,0.92))]" />
      <div className="pointer-events-none absolute inset-0 z-0 opacity-[0.16] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:72px_72px]" />

      <section className="relative z-10 flex min-h-dvh w-full max-w-none flex-col px-3 py-4 sm:px-4 sm:py-5 lg:px-5 xl:px-6">
        <header className="flex min-w-0 items-center justify-between gap-4">
          <div className="rounded-[26px] border border-white/10 bg-[#051425]/90 p-3 shadow-[0_24px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
            <img
              alt="Yudai Labs"
              className="h-auto w-36 sm:w-44"
              src="/assets/baseLogo.png"
            />
          </div>
          <a
            className="hidden min-h-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm font-medium text-fg transition-[background-color,border-color,transform] duration-150 ease-out hover:border-cyan/40 hover:bg-cyan/10 active:scale-[0.98] sm:inline-flex"
            href="/demo"
          >
            Inspect demo
          </a>
        </header>

        <div className="grid flex-1 content-center gap-6 py-8 lg:grid-cols-[minmax(0,1.04fr)_minmax(420px,0.86fr)] lg:items-center lg:gap-8 lg:py-10 2xl:grid-cols-[minmax(0,1.08fr)_minmax(520px,0.82fr)]">
          <div className="min-w-0">
            <div className="mb-6 inline-flex min-h-10 items-center gap-2 rounded-full border border-cyan/20 bg-cyan/10 px-4 text-sm font-medium text-cyan">
              <Sparkles aria-hidden="true" className="size-4" />
              Repository automation workspace
            </div>

            <h1 className="max-w-5xl text-balance text-5xl font-semibold tracking-normal text-fg sm:text-6xl lg:text-7xl 2xl:text-8xl">
              Create reviewable pull requests from GitHub issues.
            </h1>
            <p className="mt-6 max-w-3xl text-pretty text-lg leading-8 text-fg-secondary 2xl:text-xl 2xl:leading-9">
              Yudai helps engineers turn issue context into an Architect plan, Tester evidence, and a Coder pull request while keeping affected systems and reviewer expectations visible.
            </p>

            <div className="mt-7 grid max-w-4xl gap-3 sm:grid-cols-3">
              {PRODUCT_POINTS.map((point) => (
                <div
                  className="flex min-h-12 min-w-0 items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-3 text-sm text-fg-secondary backdrop-blur"
                  key={point}
                >
                  <CheckCircle2 aria-hidden="true" className="size-4 shrink-0 text-emerald-300" />
                  <span className="min-w-0 text-pretty">{point}</span>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white px-5 pl-5 pr-4 text-sm font-semibold text-black shadow-[0_18px_48px_rgba(255,255,255,0.14)] transition-[background-color,transform] duration-150 ease-out hover:bg-cyan-50 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 sm:w-auto"
                disabled={isLoading}
                onClick={() => void handleLogin()}
                type="button"
              >
                {isLoading ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Github aria-hidden="true" className="size-4" />}
                Continue with GitHub
                <ArrowRight aria-hidden="true" className="size-4" />
              </button>
              <a
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-5 text-sm font-semibold text-fg transition-[background-color,border-color,transform] duration-150 ease-out hover:border-cyan/40 hover:bg-cyan/10 active:scale-[0.97] sm:w-auto"
                href="/demo"
              >
                <PlayCircle aria-hidden="true" className="size-4 text-cyan" />
                View dummy workspace
              </a>
            </div>

            {visibleError && (
              <div className="mt-5 max-w-xl rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {visibleError}
              </div>
            )}

            <div className="mt-10 grid w-full max-w-2xl grid-cols-[repeat(3,minmax(0,1fr))] gap-2 sm:gap-3">
              {STATS.map((stat) => (
                <div
                  className="min-w-0 rounded-2xl border border-white/10 bg-[#08111d]/72 p-3 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur sm:p-4"
                  key={stat.label}
                >
                  <div className="truncate text-base font-semibold tabular-nums text-fg sm:text-2xl">{stat.value}</div>
                  <div className="mt-1 truncate text-xs uppercase tracking-normal text-fg-muted">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="min-w-0 lg:justify-self-end">
            <div className="overflow-hidden rounded-[30px] border border-white/10 bg-[#051425]/88 shadow-[0_30px_80px_rgba(0,0,0,0.42)] backdrop-blur-xl lg:w-full">
              <video
                aria-label="Yudai product walkthrough"
                autoPlay
                className="aspect-video w-full bg-black object-cover"
                controls
                loop
                muted
                playsInline
                poster="/assets/baseLogo.png"
                preload="metadata"
              >
                <source src="/videos/yudai-enterprise-intro.mp4" type="video/mp4" />
              </video>
              <div className="border-t border-white/10 bg-white/[0.035] p-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.22em] text-cyan">Live flow</p>
                    <h2 className="mt-2 text-lg font-semibold text-fg">Issue to PR pipeline</h2>
                  </div>
                  <GitPullRequestArrow aria-hidden="true" className="size-5 shrink-0 text-emerald-300" />
                </div>
                <p className="mt-3 text-sm leading-6 text-fg-secondary">
                  The workspace keeps issue details, user clarifications, affected systems, tests, and PR outputs in one inspectable run.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-3 pb-5 lg:grid-cols-3">
          {MODE_OVERVIEWS.map((mode, index) => {
            const Icon = mode.icon;

            return (
              <article
                className="min-w-0 rounded-[24px] border border-white/10 bg-[#08111d]/76 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur"
                key={mode.label}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="grid size-11 shrink-0 place-items-center rounded-2xl border border-cyan/20 bg-cyan/10 text-cyan">
                    <Icon aria-hidden="true" className="size-5" />
                  </div>
                  <span className="font-mono text-xs text-fg-muted">0{index + 1}</span>
                </div>
                <div className="mt-5">
                  <p className="text-xs uppercase tracking-[0.22em] text-fg-muted">{mode.value}</p>
                  <h3 className="mt-2 text-lg font-semibold text-fg">{mode.label}</h3>
                  <p className="mt-3 text-sm leading-6 text-fg-secondary">{mode.description}</p>
                </div>
              </article>
            );
          })}
        </div>

        <div className="pb-2 text-xs text-fg-muted">
          Architect creates the plan. Tester produces evidence. Coder ships the PR.
        </div>
      </section>
    </main>
  );
}
