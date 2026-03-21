import { useEffect, useState } from 'react';
import { API, buildApiUrl } from '../config/api';
import { useRepository } from '../hooks/useRepository';
import { useAuthStore } from '../stores/authStore';
import { useSessionStore } from '../stores/sessionStore';
import type {
  ExecutionResponse,
  ExecutionStatusResponse,
} from '../types/sessionTypes';

const modeColor: Record<string, string> = {
  architect: 'text-cyan border-cyan/30 bg-cyan/10',
  tester: 'text-amber border-amber/30 bg-amber/10',
  coder: 'text-success border-success/30 bg-success/10',
};

const apiCall = async (url: string, options?: RequestInit) => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = useAuthStore.getState().sessionToken;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    const errorMessage =
      typeof errorData?.detail === 'object' && errorData.detail !== null
        ? errorData.detail.message || errorData.detail.detail || response.statusText
        : errorData.detail || errorData.message || response.statusText;
    throw new Error(errorMessage || 'Request failed');
  }

  return response.json();
};

interface GitHubIssue {
  number: number;
  title: string;
  body?: string;
  state: string;
  html_url: string;
  created_at: string;
  updated_at: string;
  labels: string[];
  comments: number;
}

interface IssueModalProps {
  issue: GitHubIssue;
  isLoading: boolean;
  onClose: () => void;
  onStartExecution: (issue: GitHubIssue, options: { prioritizeTests: boolean; bestEffort: boolean }) => void;
}

function IssueModal({ issue, isLoading, onClose, onStartExecution }: IssueModalProps) {
  const [prioritizeTests, setPrioritizeTests] = useState(true);
  const [bestEffort, setBestEffort] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-bg-secondary shadow-terminal animate-fade-in">
        <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-border bg-bg-secondary p-6">
          <div>
            <h2 className="text-xl font-mono font-semibold text-fg">#{issue.number} {issue.title}</h2>
            <a
              href={issue.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-xs font-mono text-amber hover:text-amber/80"
            >
              View on GitHub
            </a>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-muted hover:bg-bg-tertiary hover:text-fg"
            disabled={isLoading}
          >
            &times;
          </button>
        </div>

        <div className="space-y-6 p-6">
          <div>
            <p className="mb-2 text-xs font-mono uppercase tracking-wider text-muted">Issue Description</p>
            <div className="rounded-xl border border-border bg-bg-tertiary p-4">
              <p className="whitespace-pre-wrap text-sm font-mono leading-relaxed text-fg">
                {issue.body || 'No description provided'}
              </p>
            </div>
          </div>

          <div className="space-y-3 border-t border-border pt-4">
            <p className="text-xs font-mono uppercase tracking-wider text-muted">Execution Notes</p>

            <label className="flex items-start gap-3 rounded-lg border border-border bg-bg-tertiary p-3">
              <input
                type="checkbox"
                checked={prioritizeTests}
                onChange={(event) => setPrioritizeTests(event.target.checked)}
                className="mt-1 h-4 w-4 accent-amber"
                disabled={isLoading}
              />
              <span>
                <span className="block text-sm font-mono text-fg">Prioritize tests first</span>
                <span className="text-xs font-mono text-muted">
                  Add an explicit note that the tester phase should aggressively cover regressions.
                </span>
              </span>
            </label>

            <label className="flex items-start gap-3 rounded-lg border border-border bg-bg-tertiary p-3">
              <input
                type="checkbox"
                checked={bestEffort}
                onChange={(event) => setBestEffort(event.target.checked)}
                className="mt-1 h-4 w-4 accent-amber"
                disabled={isLoading}
              />
              <span>
                <span className="block text-sm font-mono text-fg">Best effort implementation</span>
                <span className="text-xs font-mono text-muted">
                  Tell the pipeline to keep going when repository quality is uneven, but still report blockers.
                </span>
              </span>
            </label>
          </div>
        </div>

        <div className="sticky bottom-0 flex justify-end gap-3 border-t border-border bg-bg-secondary p-6">
          <button
            onClick={onClose}
            className="rounded-lg border border-border bg-bg-tertiary px-4 py-2.5 text-sm font-mono text-fg"
            disabled={isLoading}
          >
            Close
          </button>
          <button
            onClick={() => onStartExecution(issue, { prioritizeTests, bestEffort })}
            className="rounded-lg bg-amber px-6 py-2.5 text-sm font-mono font-semibold text-bg-primary glow-amber disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? 'Starting Execution...' : 'Start Execution'}
          </button>
        </div>
      </div>
    </div>
  );
}

const terminalStatuses = new Set(['complete', 'failed', 'cancelled']);

export function SolveIssues() {
  const { selectedRepository } = useRepository();
  const {
    activeSessionId,
    runtimeStatus,
    setRuntimeState,
    syncRuntimeState,
    setActiveTab,
  } = useSessionStore((state) => ({
    activeSessionId: state.activeSessionId,
    runtimeStatus: state.runtimeStatus,
    setRuntimeState: state.setRuntimeState,
    syncRuntimeState: state.syncRuntimeState,
    setActiveTab: state.setActiveTab,
  }));

  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<GitHubIssue | null>(null);
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatusResponse | null>(null);
  const [filterYudai, setFilterYudai] = useState<'all' | 'yudai' | 'others'>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRepository) return;

    const fetchIssues = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const repoOwner = selectedRepository.repository.owner?.login
          || selectedRepository.repository.full_name.split('/')[0];
        const repoName = selectedRepository.repository.name;
        const data = await apiCall(`/api/daifu/github/repositories/${repoOwner}/${repoName}/issues`);
        setIssues(data as GitHubIssue[]);
      } catch (err) {
        const fetchError = err as Error;
        setError(fetchError.message || 'Failed to fetch issues');
      } finally {
        setIsLoading(false);
      }
    };

    void fetchIssues();
  }, [selectedRepository]);

  useEffect(() => {
    if (!activeSessionId) return;

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchExecutionStatus = async () => {
      try {
        const data = await apiCall(
          buildApiUrl(API.SESSIONS.EXECUTION, { sessionId: activeSessionId }),
          { method: 'GET' }
        );
        const nextStatus = data as ExecutionStatusResponse;
        setExecutionStatus(nextStatus.execution_id ? nextStatus : null);
      } catch (err) {
        console.error('Failed to fetch execution status:', err);
      }
    };

    void fetchExecutionStatus();
    intervalId = setInterval(() => {
      void fetchExecutionStatus();
    }, 3000);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [activeSessionId]);

  const handleStartExecution = async (
    issue: GitHubIssue,
    options: { prioritizeTests: boolean; bestEffort: boolean }
  ) => {
    if (!activeSessionId || !selectedRepository) {
      setError('No active session or repository selected');
      return;
    }

    const shouldMarkProvisioning =
      runtimeStatus === 'not_provisioned'
      || runtimeStatus === 'failed'
      || runtimeStatus === 'terminated'
      || runtimeStatus === 'stopped';

    try {
      setIsLoading(true);
      setError(null);

      if (shouldMarkProvisioning) {
        setRuntimeState(null, 'provisioning', null);
      }

      const objectiveParts = [
        `Resolve GitHub issue #${issue.number}: ${issue.title}`,
        issue.body ? `Issue details:\n${issue.body}` : '',
        `Repository: ${selectedRepository.repository.full_name}@${selectedRepository.branch || 'main'}`,
        options.prioritizeTests ? 'Prioritize regression coverage and durable tests before implementation.' : '',
        options.bestEffort ? 'Continue in best-effort mode and report blockers explicitly if the repository is inconsistent.' : '',
      ].filter(Boolean);

      const data = await apiCall(
        buildApiUrl(API.SESSIONS.EXECUTION, { sessionId: activeSessionId }),
        {
          method: 'POST',
          body: JSON.stringify({ objective: objectiveParts.join('\n\n') }),
        }
      );

      const response = data as ExecutionResponse;
      void syncRuntimeState(activeSessionId).catch((runtimeError) => {
        console.warn('Failed to refresh runtime state after execution start:', runtimeError);
      });

      setExecutionStatus(response);
      setSelectedIssue(null);
      setActiveTab('ideas');
    } catch (err) {
      void syncRuntimeState(activeSessionId).catch((runtimeError) => {
        console.warn('Failed to refresh runtime state after execution error:', runtimeError);
      });
      const startError = err as Error;
      setError(startError.message || 'Failed to start execution');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelExecution = async () => {
    if (!activeSessionId) return;

    try {
      await apiCall(
        buildApiUrl(API.SESSIONS.EXECUTION_CANCEL, { sessionId: activeSessionId }),
        { method: 'POST' }
      );
      setExecutionStatus((previous) => previous ? { ...previous, status: 'cancelled', cancel_requested: true } : previous);
    } catch (err) {
      console.error('Failed to cancel execution:', err);
    }
  };

  const filteredIssues = issues.filter((issue) => {
    if (filterYudai === 'yudai') return issue.labels.includes('chat-generated');
    if (filterYudai === 'others') return !issue.labels.includes('chat-generated');
    return true;
  });

  const totalYudaiIssues = issues.filter((issue) => issue.labels.includes('chat-generated')).length;
  const totalOtherIssues = issues.length - totalYudaiIssues;

  if (!selectedRepository) {
    return (
      <div className="flex h-full items-center justify-center bg-bg terminal-noise">
        <div className="text-center animate-fade-in">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-xl border border-border bg-bg-tertiary">
            <span className="font-mono text-xl text-muted">#</span>
          </div>
          <p className="text-lg font-mono text-fg">No repository selected</p>
          <p className="mt-2 text-sm font-mono text-muted">Choose a repository before starting execution.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-bg terminal-noise">
      <div className="border-b border-border/70 bg-[linear-gradient(115deg,rgba(245,158,11,0.08)_0%,rgba(34,211,238,0.03)_40%,rgba(17,17,19,0.92)_100%)] px-4 py-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="mb-1 text-[11px] font-mono uppercase tracking-[0.18em] text-cyan">Execution</p>
            <h2 className="text-base font-mono font-semibold text-fg">Fixed 3-Mode Pipeline</h2>
            <p className="mt-1 text-xs font-mono text-fg-secondary">
              Pick one issue and launch the sequential Architect, Tester, and Coder workflow.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="rounded-md border border-border bg-bg-tertiary px-2.5 py-1 text-fg-secondary">
              {issues.length} issues
            </span>
          </div>
        </div>

        {executionStatus && executionStatus.execution_id && (() => {
          const execStatus = (executionStatus.status || 'idle').toLowerCase();
          const isTerminal = terminalStatuses.has(execStatus);
          const mode = (executionStatus.mode || '').toLowerCase();
          const modeClass = modeColor[mode] || 'text-muted border-border bg-bg-tertiary';
          return (
            <div className="mt-3 flex items-center gap-3 rounded-lg border border-border/60 bg-bg-tertiary/60 px-3 py-2">
              {!isTerminal && (
                <span className="relative flex h-2 w-2 flex-shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan" />
                </span>
              )}
              {mode && (
                <span className={`rounded-md border px-2 py-0.5 text-xs font-mono uppercase ${modeClass}`}>
                  {mode}
                </span>
              )}
              <span className="text-xs font-mono text-fg-secondary flex-1">
                {execStatus}
                {executionStatus.detail ? ` — ${executionStatus.detail}` : ''}
              </span>
              {!isTerminal && (
                <button
                  onClick={handleCancelExecution}
                  className="rounded-md border border-error/30 bg-error/10 px-2.5 py-1 text-xs font-mono text-error hover:bg-error/20"
                >
                  Cancel
                </button>
              )}
            </div>
          );
        })()}
      </div>

      <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3 font-mono text-xs">
        <button
          onClick={() => setFilterYudai('all')}
          className={`rounded-md border px-3 py-1.5 ${filterYudai === 'all' ? 'border-amber/40 bg-amber/10 text-amber' : 'border-border bg-bg-tertiary text-fg-secondary'}`}
        >
          All ({issues.length})
        </button>
        <button
          onClick={() => setFilterYudai('yudai')}
          className={`rounded-md border px-3 py-1.5 ${filterYudai === 'yudai' ? 'border-amber/40 bg-amber/10 text-amber' : 'border-border bg-bg-tertiary text-fg-secondary'}`}
        >
          Yudai ({totalYudaiIssues})
        </button>
        <button
          onClick={() => setFilterYudai('others')}
          className={`rounded-md border px-3 py-1.5 ${filterYudai === 'others' ? 'border-amber/40 bg-amber/10 text-amber' : 'border-border bg-bg-tertiary text-fg-secondary'}`}
        >
          Others ({totalOtherIssues})
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="mb-4 rounded-xl border border-error/30 bg-error/10 p-4 text-sm font-mono text-error">
            {error}
          </div>
        )}

        {filteredIssues.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <p className="text-lg font-mono text-fg">No issues available</p>
              <p className="mt-2 text-sm font-mono text-muted">Open GitHub issues will appear here for execution.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredIssues.map((issue) => (
              <button
                key={issue.number}
                onClick={() => setSelectedIssue(issue)}
                className="w-full rounded-xl border border-border bg-bg-secondary/80 p-4 text-left transition-colors hover:border-border-accent hover:bg-bg-tertiary"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="rounded-md border border-border bg-bg-tertiary px-2 py-0.5 text-xs font-mono text-fg-secondary">
                        #{issue.number}
                      </span>
                      <span className="rounded-md border border-border bg-bg-tertiary px-2 py-0.5 text-xs font-mono text-fg-secondary">
                        {issue.state}
                      </span>
                    </div>
                    <h3 className="truncate text-sm font-mono font-semibold text-fg">{issue.title}</h3>
                    <p className="mt-2 line-clamp-3 text-xs font-mono leading-relaxed text-fg-secondary">
                      {issue.body || 'No description provided'}
                    </p>
                  </div>
                  <div className="text-right text-xs font-mono text-muted">
                    <p>{issue.comments} comments</p>
                    <p className="mt-1">{new Date(issue.updated_at).toLocaleDateString()}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedIssue && (
        <IssueModal
          issue={selectedIssue}
          isLoading={isLoading}
          onClose={() => setSelectedIssue(null)}
          onStartExecution={handleStartExecution}
        />
      )}
    </div>
  );
}
