import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  Database,
  ExternalLink,
  FileCheck2,
  FolderGit2,
  GitBranch,
  Github,
  GitPullRequestArrow,
  Layers3,
  MessageSquareText,
  Network,
  Play,
  Search,
  Send,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

type DemoView = 'chat' | 'context' | 'runs' | 'issues';
type Tone = 'cyan' | 'emerald' | 'sky' | 'zinc';

type DemoIssue = {
  body: string;
  labels: string[];
  number: number;
  state: string;
  title: string;
  updated: string;
};

type DemoMode = {
  description: string;
  icon: LucideIcon;
  label: string;
  output: string;
  status: string;
  tone: Tone;
};

const DEMO_TABS: Array<{ icon: LucideIcon; id: DemoView; label: string }> = [
  { id: 'chat', label: 'Chat', icon: MessageSquareText },
  { id: 'context', label: 'Context', icon: Layers3 },
  { id: 'runs', label: 'Runs', icon: TerminalSquare },
  { id: 'issues', label: 'Issues', icon: GitPullRequestArrow },
];

const WORKSPACE_METRICS: Array<{ icon: LucideIcon; label: string; value: string }> = [
  { icon: MessageSquareText, label: 'Msgs', value: '12' },
  { icon: Database, label: 'Tokens', value: '8.4k' },
  { icon: Layers3, label: 'Ctx', value: '3' },
  { icon: GitPullRequestArrow, label: 'Issues', value: '3' },
];

const DEMO_ISSUES: DemoIssue[] = [
  {
    body: 'OAuth callback state can be dropped when the user returns from GitHub after selecting a repository.',
    labels: ['bug', 'auth', 'session'],
    number: 182,
    state: 'open',
    title: 'Preserve auth callback state through repository selection',
    updated: '2h ago',
  },
  {
    body: 'The execution tab should show what Architect, Tester, and Coder contributed before the PR is opened.',
    labels: ['ux', 'workflow'],
    number: 179,
    state: 'open',
    title: 'Show mode handoff evidence in the PR workflow',
    updated: '1d ago',
  },
  {
    body: 'Repository context cards need clearer source labels and durable selection state.',
    labels: ['frontend'],
    number: 175,
    state: 'open',
    title: 'Improve context card readability for repository automation',
    updated: '3d ago',
  },
];

const DEMO_MODES: DemoMode[] = [
  {
    description: 'Scoped the issue to auth callback persistence, session metadata, and repository selection recovery.',
    icon: Network,
    label: 'Architect',
    output: 'Affected systems: auth, sessions, repository picker',
    status: 'Complete',
    tone: 'emerald',
  },
  {
    description: 'Added regression expectations for callback redirects and token restoration after repository selection.',
    icon: ShieldCheck,
    label: 'Tester',
    output: 'Evidence branch: tests/auth-callback-state',
    status: 'Complete',
    tone: 'emerald',
  },
  {
    description: 'Applying the patch and preparing a reviewable PR with touched files and validation notes.',
    icon: Code2,
    label: 'Coder',
    output: 'PR draft: yudai/auth-callback-state',
    status: 'Running',
    tone: 'cyan',
  },
];

const DEMO_MESSAGES = [
  {
    body: 'I selected issue #182. Please prepare a small PR and explain which systems change.',
    role: 'user',
    time: '11:08',
  },
  {
    body: 'I need one clarification before starting: should the callback recovery prefer session metadata or URL state?',
    role: 'assistant',
    time: '11:09',
  },
  {
    body: 'Use session metadata first. Keep URL state as a compatibility fallback.',
    role: 'user',
    time: '11:10',
  },
  {
    body: 'Captured. The run will preserve existing OAuth behavior and report auth, session, and repository picker impact in the PR.',
    role: 'assistant',
    time: '11:10',
  },
];

const CONTEXT_ITEMS = [
  {
    detail: 'OAuth callback writes the GitHub session token and then routes into the protected workspace.',
    source: 'AuthSuccess.tsx',
    title: 'Callback state handling',
  },
  {
    detail: 'Repository selection is restored through session store state after authentication completes.',
    source: 'sessionStore.ts',
    title: 'Repository selection state',
  },
  {
    detail: 'The workbench now expects issue, affected systems, acceptance criteria, tests, and PR metadata.',
    source: 'AgentWorkbench.tsx',
    title: 'PR readiness contract',
  },
];

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function getToneClass(tone: Tone): string {
  return {
    cyan: 'border-cyan/25 bg-cyan/10 text-cyan',
    emerald: 'border-emerald-300/25 bg-emerald-400/10 text-emerald-200',
    sky: 'border-sky-300/25 bg-sky-400/10 text-sky-200',
    zinc: 'border-white/10 bg-white/[0.04] text-fg-secondary',
  }[tone];
}

function DemoBadge({ children, tone = 'zinc' }: { children: string; tone?: Tone }): JSX.Element {
  return (
    <span className={cx('inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-medium', getToneClass(tone))}>
      {children}
    </span>
  );
}

export function DemoWorkbench(): JSX.Element {
  const [activeView, setActiveView] = useState<DemoView>('chat');
  const selectedIssue = DEMO_ISSUES[0];

  return (
    <main className="relative min-h-dvh overflow-x-hidden bg-bg text-fg">
      <div className="fixed inset-0 -z-10 bg-[linear-gradient(180deg,rgba(5,12,24,0.94),rgba(10,10,11,0.98)),radial-gradient(circle_at_12%_20%,rgba(34,211,238,0.14),transparent_28%),radial-gradient(circle_at_82%_10%,rgba(16,185,129,0.12),transparent_30%)]" />
      <div className="fixed inset-0 -z-10 opacity-[0.12] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:72px_72px]" />

      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#08111d]/82 backdrop-blur-xl">
        <div className="flex min-h-20 w-full max-w-none items-center justify-between gap-4 px-3 sm:px-4 lg:px-5 xl:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="rounded-[24px] border border-white/10 bg-[#051425] p-2 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
              <img alt="Yudai Labs" className="h-auto w-36" src="/assets/baseLogo.png" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold text-fg sm:text-lg">Yudai Demo Workspace</h1>
              <p className="truncate text-sm text-fg-muted">Dummy data for issue-guided PR automation</p>
            </div>
          </div>

          <div className="hidden items-center gap-2 md:flex">
            <DemoBadge tone="cyan">Public demo</DemoBadge>
            <DemoBadge tone="emerald">PR ready: 72%</DemoBadge>
            <a
              className="inline-flex min-h-10 items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-3 text-sm font-medium text-fg transition-[background-color,border-color,transform] duration-150 hover:border-cyan/40 hover:bg-cyan/10 active:scale-[0.98]"
              href="/auth/login"
            >
              Login
              <ChevronRight aria-hidden="true" className="size-4" />
            </a>
          </div>
        </div>
      </header>

      <div className="grid w-full max-w-none gap-4 px-3 py-4 sm:px-4 lg:grid-cols-[minmax(250px,18vw)_minmax(0,1fr)] lg:px-5 xl:grid-cols-[minmax(280px,18vw)_minmax(0,1fr)_minmax(300px,20vw)] xl:px-6 2xl:grid-cols-[minmax(300px,17vw)_minmax(0,1fr)_minmax(320px,19vw)]">
        <aside className="min-w-0 rounded-[28px] border border-white/10 bg-[#08111d]/78 p-4 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-cyan">Repository</p>
              <h2 className="mt-2 text-lg font-semibold text-fg">octocat/yudaiv3</h2>
            </div>
            <Github aria-hidden="true" className="size-5 text-fg-secondary" />
          </div>

          <div className="mt-5 grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center gap-2 text-sm text-fg-secondary">
                <GitBranch aria-hidden="true" className="size-4 text-cyan" />
                main
              </div>
              <p className="mt-2 text-xs leading-5 text-fg-muted">42 commits ahead of production mirror</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center gap-2 text-sm text-fg-secondary">
                <FolderGit2 aria-hidden="true" className="size-4 text-sky-300" />
                React + FastAPI
              </div>
              <p className="mt-2 text-xs leading-5 text-fg-muted">Frontend, controller, and Daifu session APIs</p>
            </div>
          </div>

          <div className="mt-6">
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted" />
              <input
                className="h-11 w-full rounded-2xl border border-white/10 bg-white/[0.04] pl-10 pr-3 text-sm text-fg placeholder:text-fg-muted"
                defaultValue="auth callback"
                readOnly
              />
            </div>
          </div>

          <div className="mt-5 grid gap-2">
            {DEMO_ISSUES.map((issue) => (
              <button
                className={cx(
                  'rounded-2xl border p-3 text-left transition-[background-color,border-color,transform] duration-150 active:scale-[0.99]',
                  issue.number === selectedIssue.number
                    ? 'border-cyan/35 bg-cyan/10'
                    : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]'
                )}
                key={issue.number}
                onClick={() => setActiveView('issues')}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-cyan">#{issue.number}</span>
                  <span className="text-xs text-fg-muted">{issue.updated}</span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm font-medium leading-5 text-fg">{issue.title}</p>
              </button>
            ))}
          </div>
        </aside>

        <section className="min-w-0 rounded-[30px] border border-white/10 bg-[#08111d]/78 shadow-[0_30px_80px_rgba(0,0,0,0.30)] backdrop-blur-xl">
          <div className="border-b border-white/10 p-4">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-start">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-[0.22em] text-cyan">Workspace</p>
                <h2 className="mt-2 truncate text-2xl font-semibold text-fg">Issue #{selectedIssue.number}: {selectedIssue.title}</h2>
              </div>
              <WorkspaceMetrics />
            </div>

            <div className="mt-4 grid grid-cols-4 gap-2">
              {DEMO_TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = tab.id === activeView;

                return (
                  <button
                    className={cx(
                      'inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl border px-3 text-sm font-medium transition-[background-color,border-color,transform] duration-150 active:scale-[0.98]',
                      isActive
                        ? 'border-cyan/35 bg-cyan/12 text-fg shadow-[0_0_24px_rgba(34,211,238,0.12)]'
                        : 'border-white/10 bg-white/[0.035] text-fg-secondary hover:border-white/20 hover:bg-white/[0.06] hover:text-fg'
                    )}
                    key={tab.id}
                    onClick={() => setActiveView(tab.id)}
                    type="button"
                  >
                    <Icon aria-hidden="true" className="size-4" />
                    <span className="hidden sm:inline">{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="min-h-[620px] p-4">
            {activeView === 'chat' && <DemoChat />}
            {activeView === 'context' && <DemoContext />}
            {activeView === 'runs' && <DemoRuns selectedIssue={selectedIssue} />}
            {activeView === 'issues' && <DemoIssues selectedIssue={selectedIssue} />}
          </div>
        </section>

        <aside className="grid auto-rows-max gap-4 lg:col-span-2 xl:col-span-1">
          <RightPanel title="Session" eyebrow="Runtime">
            <div className="grid gap-3">
              <ReadinessRow complete label="Repository selected" />
              <ReadinessRow complete label="Issue selected" />
              <ReadinessRow complete label="Affected systems recorded" />
              <ReadinessRow label="Coder PR pending" />
            </div>
          </RightPanel>

          <RightPanel title="PR readiness" eyebrow="Review">
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-fg-secondary">Readiness</span>
                  <span className="font-mono text-cyan">72%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-[72%] rounded-full bg-cyan" />
                </div>
              </div>
              <div className="grid gap-2 text-sm text-fg-secondary">
                <p>Affected systems: auth, sessions, repository picker</p>
                <p>Tests: callback redirect regression, token restore flow</p>
                <p>PR target: <span className="font-mono text-fg">main</span></p>
              </div>
            </div>
          </RightPanel>

          <RightPanel title="PR preview" eyebrow="Output">
            <a
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-black transition-[background-color,transform] duration-150 hover:bg-cyan-50 active:scale-[0.98]"
              href="https://github.com/octocat/yudaiv3/pull/204"
              rel="noreferrer"
              target="_blank"
            >
              Open dummy PR
              <ExternalLink aria-hidden="true" className="size-4" />
            </a>
          </RightPanel>
        </aside>
      </div>
    </main>
  );
}

function WorkspaceMetrics(): JSX.Element {
  return (
    <div className="grid w-full grid-cols-2 gap-2 sm:grid-cols-4 xl:w-auto xl:justify-end">
      {WORKSPACE_METRICS.map((metric) => (
        <Metric
          icon={metric.icon}
          key={metric.label}
          label={metric.label}
          value={metric.value}
        />
      ))}
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }): JSX.Element {
  return (
    <div className="grid min-h-[64px] min-w-[92px] grid-rows-[1fr_auto] rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2.5 xl:w-[104px] 2xl:w-[118px]">
      <div className="flex items-center justify-between gap-2">
        <Icon aria-hidden="true" className="size-4 shrink-0 text-cyan" />
        <span className="whitespace-nowrap font-mono text-lg font-semibold tabular-nums text-fg">{value}</span>
      </div>
      <p className="mt-1 whitespace-nowrap text-[10px] uppercase tracking-normal text-fg-muted">{label}</p>
    </div>
  );
}

function DemoChat(): JSX.Element {
  return (
    <div className="flex min-h-[590px] flex-col">
      <div className="flex-1 space-y-3">
        {DEMO_MESSAGES.map((message) => (
          <div
            className={cx(
              'max-w-[82%] rounded-[24px] border p-4',
              message.role === 'user'
                ? 'ml-auto border-cyan/25 bg-cyan/10'
                : 'border-white/10 bg-white/[0.04]'
            )}
            key={`${message.role}-${message.time}-${message.body}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs uppercase tracking-[0.18em] text-fg-muted">{message.role}</span>
              <span className="font-mono text-xs text-fg-muted">{message.time}</span>
            </div>
            <p className="mt-2 text-sm leading-6 text-fg-secondary">{message.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-[24px] border border-white/10 bg-white/[0.035] p-3">
        <div className="flex gap-3">
          <input
            className="min-h-12 flex-1 rounded-2xl border border-white/10 bg-[#08111d] px-4 text-sm text-fg placeholder:text-fg-muted"
            placeholder="Ask for more context before the PR is created"
            readOnly
          />
          <button
            className="inline-flex min-h-12 items-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-black"
            type="button"
          >
            <Send aria-hidden="true" className="size-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function DemoContext(): JSX.Element {
  return (
    <div className="grid gap-3">
      {CONTEXT_ITEMS.map((item) => (
        <article className="rounded-[24px] border border-white/10 bg-white/[0.035] p-5" key={item.title}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-cyan">{item.source}</p>
              <h3 className="mt-2 text-lg font-semibold text-fg">{item.title}</h3>
            </div>
            <FileCheck2 aria-hidden="true" className="size-5 shrink-0 text-emerald-300" />
          </div>
          <p className="mt-3 text-sm leading-6 text-fg-secondary">{item.detail}</p>
        </article>
      ))}
    </div>
  );
}

function DemoRuns({ selectedIssue }: { selectedIssue: DemoIssue }): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="rounded-[24px] border border-white/10 bg-white/[0.035] p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-cyan">Execution objective</p>
            <h3 className="mt-2 text-xl font-semibold text-fg">Resolve issue #{selectedIssue.number}</h3>
          </div>
          <button className="inline-flex min-h-10 items-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-black" type="button">
            <Play aria-hidden="true" className="size-4" />
            Running
          </button>
        </div>
        <p className="mt-3 text-sm leading-6 text-fg-secondary">{selectedIssue.body}</p>
      </div>

      <div className="grid gap-3">
        {DEMO_MODES.map((mode, index) => {
          const Icon = mode.icon;

          return (
            <article className="rounded-[24px] border border-white/10 bg-white/[0.035] p-5" key={mode.label}>
              <div className="flex items-start gap-4">
                <div className={cx('grid size-11 shrink-0 place-items-center rounded-2xl border', getToneClass(mode.tone))}>
                  <Icon aria-hidden="true" className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs text-fg-muted">0{index + 1}</p>
                      <h3 className="mt-1 text-lg font-semibold text-fg">{mode.label}</h3>
                    </div>
                    <DemoBadge tone={mode.tone}>{mode.status}</DemoBadge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-fg-secondary">{mode.description}</p>
                  <p className="mt-3 rounded-2xl border border-white/10 bg-[#08111d] px-3 py-2 text-sm text-fg-secondary">{mode.output}</p>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function DemoIssues({ selectedIssue }: { selectedIssue: DemoIssue }): JSX.Element {
  return (
    <div className="grid gap-3">
      {DEMO_ISSUES.map((issue) => (
        <article
          className={cx(
            'rounded-[24px] border p-5',
            issue.number === selectedIssue.number
              ? 'border-cyan/35 bg-cyan/10'
              : 'border-white/10 bg-white/[0.035]'
          )}
          key={issue.number}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-mono text-xs text-cyan">#{issue.number}</p>
              <h3 className="mt-2 text-lg font-semibold text-fg">{issue.title}</h3>
            </div>
            <DemoBadge tone={issue.number === selectedIssue.number ? 'cyan' : 'zinc'}>
              {issue.number === selectedIssue.number ? 'Selected' : issue.state}
            </DemoBadge>
          </div>
          <p className="mt-3 text-sm leading-6 text-fg-secondary">{issue.body}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {issue.labels.map((label) => (
              <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-fg-secondary" key={label}>
                {label}
              </span>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function RightPanel({
  children,
  eyebrow,
  title,
}: {
  children: ReactNode;
  eyebrow: string;
  title: string;
}): JSX.Element {
  return (
    <section className="rounded-[28px] border border-white/10 bg-[#08111d]/78 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.24)] backdrop-blur">
      <p className="text-xs uppercase tracking-[0.22em] text-cyan">{eyebrow}</p>
      <h2 className="mt-2 text-lg font-semibold text-fg">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ReadinessRow({ complete = false, label }: { complete?: boolean; label: string }): JSX.Element {
  const Icon = complete ? CheckCircle2 : Clock3;

  return (
    <div className="flex items-center gap-3 text-sm text-fg-secondary">
      <Icon aria-hidden="true" className={cx('size-4', complete ? 'text-emerald-300' : 'text-cyan')} />
      <span>{label}</span>
    </div>
  );
}
