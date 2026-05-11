import { useMemo, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Code2,
  Github,
  GitPullRequestArrow,
  Loader2,
  PanelsTopLeft,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const ENTERPRISE_VIDEO_SRC = '/videos/yudai-enterprise-intro.mp4';
const BRAND_LOGO_SRC = '/assets/baseLogo.png';

const CAPABILITIES = [
  {
    copy: 'Orchestrate repository context, constraints, and adversarial objectives before execution.',
    icon: PanelsTopLeft,
    label: 'Architect',
  },
  {
    copy: 'Validate tests, contracts, and regression evidence before the patch gate opens.',
    icon: ShieldCheck,
    label: 'Tester',
  },
  {
    copy: 'Apply constrained worker edits that fit the existing codebase patterns.',
    icon: Code2,
    label: 'Coder',
  },
  {
    copy: 'Move accepted changes into GitHub with traceable decisions and review context.',
    icon: GitPullRequestArrow,
    label: 'Review',
  },
];

const PROOF_POINTS = [
  { label: 'Lifecycle roles', value: '3' },
  { label: 'Backend gate', value: 'Enforced' },
  { label: 'Runtime target', value: 'Modal' },
];

const TRUST_POINTS = [
  'Auditable context',
  'Contract-aware automation',
  'GitHub-native delivery',
];

const VIDEO_STEPS = [
  'Architect',
  'Tester',
  'Coder',
  'PR',
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
    <main className="landing-page relative isolate min-h-dvh overflow-x-hidden bg-bg text-fg">
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(135deg,rgb(6,7,9),rgb(13,18,19)_46%,rgb(12,10,14))]" />
      <video
        aria-hidden="true"
        autoPlay
        className="landing-ambient-drift landing-video-mask pointer-events-none absolute inset-y-0 -right-36 z-0 hidden h-full w-[68%] object-cover opacity-[0.16] blur-3xl brightness-[0.38] contrast-125 saturate-[1.35] xl:block"
        loop
        muted
        playsInline
        preload="metadata"
        src={ENTERPRISE_VIDEO_SRC}
      />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[linear-gradient(90deg,rgba(6,7,9,0.98)_0%,rgba(6,7,9,0.9)_42%,rgba(6,7,9,0.76)_68%,rgba(6,7,9,0.96)_100%)]" />
      <div className="landing-grid pointer-events-none absolute inset-0 z-0 opacity-35" />

      <section className="relative z-10 mx-auto grid min-h-dvh w-full max-w-7xl grid-cols-[minmax(0,1fr)] content-start gap-9 px-5 py-7 sm:px-8 sm:py-10 lg:grid-cols-[minmax(0,1fr)_minmax(360px,520px)] lg:content-center lg:items-center lg:gap-12 xl:gap-16">
        <div className="w-full min-w-0 max-w-3xl">
          <div className="landing-reveal inline-flex min-h-14 max-w-full items-center gap-3 rounded-2xl bg-white/[0.07] p-2 pr-4 shadow-[0_0_0_1px_rgba(255,255,255,0.1),0_18px_60px_rgba(0,0,0,0.28)] backdrop-blur-xl">
            <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-white text-black shadow-[0_0_0_1px_rgba(255,255,255,0.32),0_10px_28px_rgba(0,0,0,0.22)] sm:size-14">
              <img
                alt=""
                className="size-9 object-contain sm:size-10"
                src={BRAND_LOGO_SRC}
              />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-fg">Yudai</p>
              <p className="truncate text-xs text-fg-muted">Enterprise agent workspace</p>
            </div>
          </div>

          <h1 className="landing-reveal landing-delay-1 mt-8 max-w-4xl text-balance text-4xl font-semibold leading-[1.04] text-fg sm:text-5xl lg:text-6xl xl:text-7xl">
            Yudai Agent Console for adversarial GitHub workflows.
          </h1>
          <p className="landing-reveal landing-delay-2 mt-5 max-w-2xl text-pretty text-base leading-8 text-fg-secondary sm:text-lg">
            Yudai gives engineering teams a controlled Architect, Tester, and Coder lifecycle for repository changes: Daifu chat through OpenRouter, Modal-backed execution, typed contracts, and PR-ready context without losing review authority.
          </p>

          <div className="landing-reveal landing-delay-3 mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
            <button
              className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-amber px-5 pl-5 pr-4 text-sm font-semibold text-black shadow-[0_18px_42px_rgba(245,158,11,0.22),0_0_0_1px_rgba(255,255,255,0.22)_inset] transition-[background-color,box-shadow,scale] duration-150 ease-out hover:bg-yellow-400 hover:shadow-[0_22px_54px_rgba(245,158,11,0.28),0_0_0_1px_rgba(255,255,255,0.28)_inset] active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 sm:w-auto"
              disabled={isLoading}
              onClick={() => void handleLogin()}
              type="button"
            >
              {isLoading ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Github aria-hidden="true" className="size-4" />}
              Continue with GitHub
              <ArrowRight aria-hidden="true" className="size-4" />
            </button>
            <div className="flex min-w-0 items-center gap-2 text-sm text-fg-muted">
              <CheckCircle2 aria-hidden="true" className="size-4 shrink-0 text-success" />
              <span className="truncate">Built for traceable engineering work</span>
            </div>
          </div>

          {visibleError && (
            <div className="mt-5 max-w-xl rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.26)]" role="alert">
              {visibleError}
            </div>
          )}

          <div className="landing-reveal landing-delay-4 mt-10 grid w-full max-w-2xl grid-cols-[repeat(3,minmax(0,1fr))] gap-2 sm:gap-3">
            {PROOF_POINTS.map((stat) => (
              <div
                className="min-w-0 rounded-xl bg-white/[0.06] p-3 shadow-[0_0_0_1px_rgba(255,255,255,0.09),0_18px_46px_rgba(0,0,0,0.18)] backdrop-blur-md sm:p-4"
                key={stat.label}
              >
                <div className="truncate text-base font-semibold tabular-nums text-fg sm:text-2xl">{stat.value}</div>
                <div className="mt-1 truncate text-xs text-fg-muted">{stat.label}</div>
              </div>
            ))}
          </div>

          <div className="landing-reveal landing-delay-5 mt-8 grid max-w-2xl gap-3 sm:grid-cols-2">
            {CAPABILITIES.map((capability) => {
              const Icon = capability.icon;

              return (
                <div
                  className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-3 rounded-xl bg-black/[0.24] p-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] backdrop-blur-sm"
                  key={capability.label}
                >
                  <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-cyan/10 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.18)]">
                    <Icon aria-hidden="true" className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-fg">{capability.label}</div>
                    <p className="mt-1 text-pretty text-xs leading-5 text-fg-muted">{capability.copy}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="landing-reveal landing-delay-6 mt-5 flex flex-wrap gap-2">
            {TRUST_POINTS.map((point) => (
              <span
                className="inline-flex min-h-8 items-center rounded-lg bg-white/[0.06] px-3 text-xs font-medium text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
                key={point}
              >
                {point}
              </span>
            ))}
          </div>
        </div>

        <aside className="landing-reveal landing-delay-7 relative min-w-0 lg:justify-self-end">
          <div className="landing-panel-ring relative mx-auto w-full max-w-[540px] rounded-[28px] p-2">
            <div className="landing-shimmer pointer-events-none absolute inset-0 rounded-[28px]" />
            <div className="relative overflow-hidden rounded-[20px] bg-black shadow-[0_30px_90px_rgba(0,0,0,0.48)]">
              <div className="aspect-video bg-black">
                <video
                  aria-hidden="true"
                  autoPlay
                  className="image-outline h-full w-full object-contain object-center brightness-[0.9] contrast-[1.06] saturate-[1.12]"
                  loop
                  muted
                  playsInline
                  preload="metadata"
                  src={ENTERPRISE_VIDEO_SRC}
                />
              </div>
              <div className="bg-black/[0.78] p-3 shadow-[0_-1px_0_rgba(255,255,255,0.1)] sm:p-4">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="size-2 shrink-0 rounded-full bg-success shadow-[0_0_18px_rgba(16,185,129,0.9)]" />
                    <span className="truncate text-sm font-semibold text-fg">Lifecycle audit live</span>
                  </div>
                  <span className="shrink-0 rounded-md bg-white/10 px-2 py-1 text-xs text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.1)]">
                    Modal runtime
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-1.5">
                  {VIDEO_STEPS.map((step, index) => (
                    <div className="min-w-0" key={step}>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.16]">
                        <span className="block h-full rounded-full bg-cyan/80" />
                      </div>
                      <div className="mt-2 truncate text-xs text-fg-muted">
                        <span className="tabular-nums text-fg-secondary">0{index + 1}</span> {step}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
