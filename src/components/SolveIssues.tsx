import { useState, useEffect, useMemo } from 'react';
import { useRepository } from '../hooks/useRepository';
import { useAuthStore } from '../stores/authStore';
import { useSessionStore } from '../stores/sessionStore';
import { API, buildApiUrl } from '../config/api';
import { TrajectoryViewer } from './TrajectoryViewer';
import type {
  SolveStatusResponse,
  StartSolveRequest,
  StartSolveResponse,
} from '../types/sessionTypes';

// Simple API helper
const apiCall = async (url: string, options?: RequestInit) => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = useAuthStore.getState().sessionToken;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
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
    throw new Error(errorData.detail || errorData.message || 'Request failed');
  }

  return response.json();
};

// Types
interface GitHubIssue {
  number: number;
  title: string;
  body?: string;
  state: string;
  html_url: string;
  created_at: string;
  updated_at: string;
  labels: string[];
  assignee?: string;
  comments: number;
  id?: number;
}

interface AIModel {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  description?: string;
}

const isFreeModel = (model: AIModel): boolean => {
  const searchable = `${model.name} ${model.provider} ${model.model_id} ${model.description || ''}`.toLowerCase();
  return searchable.includes('free');
};

// Helper function to convert backend status (lowercase) to display format (uppercase)
const toDisplayStatus = (status: string): string => {
  return status.toUpperCase();
};

// Helper function to check if status is complete
const isCompleteStatus = (status: string): boolean => {
  const upper = status.toUpperCase();
  return ['COMPLETED', 'FAILED', 'CANCELLED'].includes(upper);
};

// Helper function to check if status can be cancelled
const canCancelStatus = (status: string): boolean => {
  const upper = status.toUpperCase();
  return ['PENDING', 'RUNNING'].includes(upper);
};

const DEFAULT_SOLVER_LIMITS = {
  max_iterations: 40,
  max_cost: 7.5,
};

interface IssueModalProps {
  issue: GitHubIssue;
  onClose: () => void;
  onStartSolve: (issueId: number, modelId: number, smallChange: boolean, bestEffort: boolean) => void;
  availableModels: AIModel[];
  isLoading: boolean;
}

function IssueModal({ issue, onClose, onStartSolve, availableModels, isLoading }: IssueModalProps) {
  const [selectedModelId, setSelectedModelId] = useState<number>(0);
  const [smallChange, setSmallChange] = useState(false);
  const [bestEffort, setBestEffort] = useState(false);
  const freeModel = useMemo(
    () => availableModels.find((model) => isFreeModel(model)),
    [availableModels]
  );
  const selectedModelStillExists = availableModels.some((model) => model.id === selectedModelId);
  const resolvedSelectedModelId = selectedModelStillExists
    ? selectedModelId
    : freeModel?.id ?? 0;
  const selectedModelDescription = availableModels.find((m) => m.id === resolvedSelectedModelId)?.description;
  const modelSelectId = `solve-model-${issue.number}`;
  const smallChangeId = `small-change-${issue.number}`;
  const bestEffortId = `best-effort-${issue.number}`;

  const isYudaiGenerated = issue.labels.includes('chat-generated');

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-bg-secondary border border-border rounded-xl shadow-terminal max-w-3xl w-full max-h-[90vh] overflow-y-auto animate-fade-in">
        {/* Header */}
        <div className="sticky top-0 bg-bg-secondary border-b border-border p-6 flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-xl font-mono font-semibold text-fg">
                #{issue.number} {issue.title}
              </h2>
              {isYudaiGenerated && (
                <span className="px-2.5 py-1 bg-amber/10 text-amber border border-amber/20 text-xs font-mono font-semibold rounded-lg">
                  Yudai Generated
                </span>
              )}
            </div>
            <a
              href={issue.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted hover:text-amber font-mono transition-colors"
            >
              View on GitHub &rarr;
            </a>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-fg p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
            disabled={isLoading}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Issue Description */}
          <div>
            <h3 className="text-xs font-mono uppercase tracking-wider text-muted mb-2">Issue Description</h3>
            <div className="bg-bg-tertiary border border-border rounded-xl p-4">
              <p className="text-fg font-mono text-sm whitespace-pre-wrap leading-relaxed">{issue.body || 'No description provided'}</p>
            </div>
          </div>

          {/* Labels */}
          {issue.labels.length > 0 && (
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-muted mb-2">Labels</h3>
              <div className="flex flex-wrap gap-2">
                {issue.labels.map((label) => (
                  <span
                    key={label}
                    className="px-2.5 py-1 bg-bg-tertiary text-fg-secondary text-xs font-mono rounded-lg border border-border"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Solve Options */}
          <div className="space-y-4 pt-4 border-t border-border">
            <h3 className="text-lg font-mono font-semibold text-fg">Solve Configuration</h3>

            {/* AI Model Selection */}
            <div>
              <label htmlFor={modelSelectId} className="block text-xs font-mono uppercase tracking-wider text-muted mb-2">
                Select AI Model
              </label>
              <select
                id={modelSelectId}
                value={resolvedSelectedModelId}
                onChange={(e) => setSelectedModelId(Number(e.target.value))}
                className="w-full bg-bg-tertiary border border-border rounded-lg px-4 py-3 text-fg font-mono text-sm focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/10 transition-all duration-200"
                disabled={isLoading || availableModels.length === 0}
              >
                <option value={0} disabled>
                  {availableModels.length === 0 ? 'No models available' : 'Select an AI model'}
                </option>
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
              {freeModel && resolvedSelectedModelId === freeModel.id && (
                <p className="text-xs text-success font-mono mt-2">
                  Free model selected by default: {freeModel.name}
                </p>
              )}
              {selectedModelDescription && (
                <p className="text-xs text-muted font-mono mt-2">
                  {selectedModelDescription}
                </p>
              )}
            </div>

            {/* Options Checkboxes */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-bg-tertiary border border-border rounded-lg hover:border-border-accent transition-colors">
                <input
                  id={smallChangeId}
                  type="checkbox"
                  checked={smallChange}
                  onChange={(e) => setSmallChange(e.target.checked)}
                  className="w-4 h-4 text-amber bg-bg border-border rounded focus:ring-amber accent-amber"
                  disabled={isLoading}
                />
                <label htmlFor={smallChangeId} className="cursor-pointer">
                  <span className="text-fg font-mono text-sm font-medium">Small Change</span>
                  <p className="text-xs text-muted font-mono">Limit scope to minimal code changes</p>
                </label>
              </div>

              <div className="flex items-center gap-3 p-3 bg-bg-tertiary border border-border rounded-lg hover:border-border-accent transition-colors">
                <input
                  id={bestEffortId}
                  type="checkbox"
                  checked={bestEffort}
                  onChange={(e) => setBestEffort(e.target.checked)}
                  className="w-4 h-4 text-amber bg-bg border-border rounded focus:ring-amber accent-amber"
                  disabled={isLoading}
                />
                <label htmlFor={bestEffortId} className="cursor-pointer">
                  <span className="text-fg font-mono text-sm font-medium">Best Effort</span>
                  <p className="text-xs text-muted font-mono">Continue solving even if tests fail</p>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-bg-secondary border-t border-border p-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2.5 bg-bg-tertiary hover:bg-border/50 text-fg rounded-lg font-mono text-sm transition-colors border border-border"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={() => issue.id && onStartSolve(issue.id, resolvedSelectedModelId, smallChange, bestEffort)}
            className="px-6 py-2.5 bg-amber hover:bg-amber/90 text-bg-primary rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed glow-amber flex items-center gap-2"
            disabled={isLoading || !resolvedSelectedModelId || !issue.id}
          >
            {isLoading && <div className="animate-spin rounded-full h-4 w-4 border-2 border-bg-primary/20 border-t-bg-primary" />}
            {isLoading ? 'Starting Solve...' : 'Start Solve'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface SolveProgressModalProps {
  solveStatus: SolveStatusResponse;
  sessionId: string;
  onClose: () => void;
  onCancel: () => void;
}

function SolveProgressModal({ solveStatus, sessionId, onClose, onCancel }: SolveProgressModalProps) {
  const [showTrajectory, setShowTrajectory] = useState(false);
  const isComplete = isCompleteStatus(solveStatus.status);
  const canCancel = canCancelStatus(solveStatus.status);

  // Find active (running) run for live trajectory
  const activeRun = solveStatus.runs.find((r) => r.status === 'running');

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-success';
      case 'RUNNING':
        return 'text-cyan';
      case 'FAILED':
        return 'text-error';
      case 'CANCELLED':
        return 'text-amber';
      default:
        return 'text-muted';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return '✓';
      case 'RUNNING':
        return '⟳';
      case 'FAILED':
        return '✗';
      case 'CANCELLED':
        return '⊗';
      default:
        return '○';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-bg-secondary border border-border rounded-xl shadow-terminal max-w-4xl w-full max-h-[90vh] overflow-y-auto animate-fade-in">
        {/* Header */}
        <div className="sticky top-0 bg-bg-secondary border-b border-border p-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-mono font-semibold text-fg">Solve Progress</h2>
            <button
              onClick={onClose}
              className="text-muted hover:text-fg p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
              disabled={!isComplete}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Progress Overview */}
        <div className="p-6 space-y-6">
          <div className="bg-bg-tertiary border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-mono font-semibold text-fg">Overall Status</h3>
                <p className={`text-sm font-mono font-medium ${getStatusColor(toDisplayStatus(solveStatus.status))}`}>
                  {toDisplayStatus(solveStatus.status)}
                </p>
              </div>
              {!isComplete && (
                <div className="animate-spin h-8 w-8 border-3 border-amber border-t-transparent rounded-full" />
              )}
            </div>

            {/* Progress Stats */}
            <div className="grid grid-cols-4 gap-4 text-center">
              <div className="bg-bg-secondary border border-border rounded-lg p-3">
                <p className="text-2xl font-mono font-bold text-fg">{solveStatus.progress.runs_total}</p>
                <p className="text-xs text-muted font-mono uppercase tracking-wider">Total Runs</p>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3">
                <p className="text-2xl font-mono font-bold text-success">{solveStatus.progress.runs_completed}</p>
                <p className="text-xs text-muted font-mono uppercase tracking-wider">Completed</p>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3">
                <p className="text-2xl font-mono font-bold text-cyan">{solveStatus.progress.runs_running}</p>
                <p className="text-xs text-muted font-mono uppercase tracking-wider">Running</p>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3">
                <p className="text-2xl font-mono font-bold text-error">{solveStatus.progress.runs_failed}</p>
                <p className="text-xs text-muted font-mono uppercase tracking-wider">Failed</p>
              </div>
            </div>

            {solveStatus.error_message && (
              <div className="mt-4 p-3 bg-error/10 border border-error/30 rounded-lg">
                <p className="text-sm text-error font-mono">{solveStatus.error_message}</p>
              </div>
            )}
          </div>

          {/* Champion Run */}
          {solveStatus.champion_run && (
            <div className="bg-success/10 border border-success/30 rounded-xl p-4 animate-fade-in">
              <h3 className="text-lg font-mono font-semibold text-success mb-2 flex items-center gap-2">
                <span>🏆</span> Champion Solution
              </h3>
              <p className="text-fg font-mono text-sm mb-2">Model: {solveStatus.champion_run.model}</p>
              {solveStatus.champion_run.pr_url && (
                <a
                  href={solveStatus.champion_run.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-amber hover:text-amber/80 font-mono text-sm underline"
                >
                  View Pull Request &rarr;
                </a>
              )}
            </div>
          )}

          {/* Individual Runs */}
          <div>
            <h3 className="text-lg font-mono font-semibold text-fg mb-3">Run Details</h3>
            <div className="space-y-3">
              {solveStatus.runs.map((run) => (
                <div
                  key={run.id}
                  className="bg-bg-tertiary border border-border rounded-xl p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className={`text-2xl ${getStatusColor(toDisplayStatus(run.status))}`}>
                        {getStatusIcon(toDisplayStatus(run.status))}
                      </span>
                      <div>
                        <p className="font-mono font-medium text-fg text-sm">{run.model}</p>
                        <p className={`text-xs font-mono ${getStatusColor(toDisplayStatus(run.status))}`}>
                          {toDisplayStatus(run.status)}
                        </p>
                      </div>
                    </div>
                    {run.pr_url && (
                      <a
                        href={run.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-amber hover:text-amber/80 font-mono underline"
                      >
                        View PR
                      </a>
                    )}
                  </div>

                  {run.error_message && (
                    <p className="text-xs text-error font-mono mt-2">{run.error_message}</p>
                  )}

                  <div className="flex gap-4 text-xs text-muted font-mono mt-2">
                    {run.started_at && (
                      <span>Started: {new Date(run.started_at).toLocaleTimeString()}</span>
                    )}
                    {run.completed_at && (
                      <span>Completed: {new Date(run.completed_at).toLocaleTimeString()}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Live Trajectory Viewer */}
          {activeRun && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-mono font-semibold text-fg">Live Trajectory</h3>
                <button
                  onClick={() => setShowTrajectory(!showTrajectory)}
                  className="px-3 py-1.5 bg-amber/10 hover:bg-amber/20 text-amber border border-amber/30 rounded-lg font-mono text-sm font-semibold transition-colors"
                >
                  {showTrajectory ? 'Hide' : 'Show'} Live Trajectory
                </button>
              </div>

              {showTrajectory && (
                <div className="bg-bg-tertiary border border-border rounded-xl overflow-hidden" style={{ height: '500px' }}>
                  <TrajectoryViewer
                    isLive
                    sessionId={sessionId}
                    solveId={solveStatus.solve_session_id}
                    runId={activeRun.id}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-bg-secondary border-t border-border p-6 flex justify-end gap-3">
          {canCancel && (
            <button
              onClick={onCancel}
              className="px-4 py-2.5 bg-error/10 hover:bg-error/20 text-error border border-error/30 rounded-lg font-mono text-sm font-semibold transition-colors"
            >
              Cancel Solve
            </button>
          )}
          {isComplete && (
            <button
              onClick={onClose}
              className="px-6 py-2.5 bg-amber hover:bg-amber/90 text-bg-primary rounded-lg font-mono text-sm font-semibold transition-all duration-200 glow-amber"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function SolveIssues() {
  const { selectedRepository } = useRepository();
  const activeSessionId = useSessionStore((state) => state.activeSessionId);

  const [issuesState, setIssuesState] = useState<{
    issues: GitHubIssue[];
    availableModels: AIModel[];
  }>({
    issues: [],
    availableModels: [],
  });
  const [solveUiState, setSolveUiState] = useState<{
    selectedIssue: GitHubIssue | null;
    activeSolveId: string | null;
    solveStatus: SolveStatusResponse | null;
  }>({
    selectedIssue: null,
    activeSolveId: null,
    solveStatus: null,
  });
  const [viewState, setViewState] = useState<{
    isLoading: boolean;
    error: string | null;
    filterYudai: 'all' | 'yudai' | 'others';
  }>({
    isLoading: false,
    error: null,
    filterYudai: 'all',
  });
  const { issues, availableModels } = issuesState;
  const { selectedIssue, activeSolveId, solveStatus } = solveUiState;
  const { isLoading, error, filterYudai } = viewState;

  // Fetch GitHub issues
  useEffect(() => {
    if (!selectedRepository) return;

    const fetchIssues = async () => {
      setViewState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        // Extract owner correctly - owner is an object, need to use .login or fallback to full_name
        const repoOwner = selectedRepository.repository.owner?.login ||
                          selectedRepository.repository.full_name.split('/')[0];
        const repoName = selectedRepository.repository.name;
        const data = await apiCall(
          `/api/daifu/github/repositories/${repoOwner}/${repoName}/issues`
        );
        setIssuesState((prev) => ({
          ...prev,
          issues: data as GitHubIssue[],
        }));
        setViewState((prev) => ({ ...prev, isLoading: false, error: null }));
      } catch (err) {
        console.error('Failed to fetch issues:', err);
        const fetchError = err as Error;
        setViewState((prev) => ({
          ...prev,
          isLoading: false,
          error: fetchError.message || 'Failed to fetch issues',
        }));
      }
    };

    void fetchIssues();
  }, [selectedRepository]);

  // Fetch available AI models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await apiCall('/api/daifu/ai-models');
        setIssuesState((prev) => ({
          ...prev,
          availableModels: data as AIModel[],
        }));
      } catch (err) {
        console.error('Failed to fetch AI models:', err);
      }
    };

    void fetchModels();
  }, []);

  // Poll solve status when active
  useEffect(() => {
    if (!activeSolveId || !activeSessionId) return;

    let intervalId: ReturnType<typeof setInterval> | null = null;

    const pollStatus = async () => {
      try {
        const data = await apiCall(
          buildApiUrl(API.SESSIONS.SOLVER.STATUS, {
            sessionId: activeSessionId,
            solveSessionId: activeSolveId,
          })
        );
        setSolveUiState((prev) => ({
          ...prev,
          solveStatus: data as SolveStatusResponse,
        }));

        // Stop polling if solve is complete
        if (isCompleteStatus((data as SolveStatusResponse).status) && intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      } catch (err) {
        console.error('Failed to fetch solve status:', err);
      }
    };

    void pollStatus();
    intervalId = setInterval(() => {
      void pollStatus();
    }, 3000); // Poll every 3 seconds

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [activeSolveId, activeSessionId]);

  const handleStartSolve = async (
    issueId: number,
    modelId: number,
    smallChange: boolean,
    bestEffort: boolean
  ) => {
    if (!activeSessionId || !selectedRepository) {
      setViewState((prev) => ({
        ...prev,
        error: 'No active session or repository selected',
      }));
      return;
    }

    try {
      setViewState((prev) => ({ ...prev, isLoading: true, error: null }));

      // Extract owner correctly - owner is an object, need to use .login or fallback to full_name
      const repoOwner = selectedRepository.repository.owner?.login ||
                        selectedRepository.repository.full_name.split('/')[0];
      const repoName = selectedRepository.repository.name;

      const solverPayload: StartSolveRequest = {
        issue_id: issueId,
        ai_model_id: modelId,
        repo_url: `https://github.com/${repoOwner}/${repoName}`,
        branch_name: selectedRepository.branch || 'main',
        small_change: smallChange,
        best_effort: bestEffort,
        max_iterations: DEFAULT_SOLVER_LIMITS.max_iterations,
        max_cost: DEFAULT_SOLVER_LIMITS.max_cost,
      };

      const data = await apiCall(buildApiUrl(API.SESSIONS.SOLVER.START, {
        sessionId: activeSessionId,
      }), {
        method: 'POST',
        body: JSON.stringify(solverPayload),
      });

      const response = data as StartSolveResponse;
      setSolveUiState((prev) => ({
        ...prev,
        activeSolveId: response.solve_session_id,
        solveStatus: {
          solve_session_id: response.solve_session_id,
          status: response.status,
          progress: {
            runs_total: 0,
            runs_completed: 0,
            runs_failed: 0,
            runs_running: 0,
            last_update: new Date().toISOString(),
            message: 'Starting solve...',
          },
          runs: [],
        },
        selectedIssue: null,
      }));
    } catch (err) {
      console.error('Failed to start solve:', err);
      const startError = err as Error;
      setViewState((prev) => ({
        ...prev,
        error: startError.message || 'Failed to start solve',
      }));
    } finally {
      setViewState((prev) => ({ ...prev, isLoading: false }));
    }
  };

  const handleCancelSolve = async () => {
    if (!activeSolveId || !activeSessionId) return;

    try {
      await apiCall(
        buildApiUrl(API.SESSIONS.SOLVER.CANCEL, {
          sessionId: activeSessionId,
          solveSessionId: activeSolveId,
        }),
        {
          method: 'POST',
        }
      );
      setSolveUiState((prev) => ({
        ...prev,
        activeSolveId: null,
        solveStatus: null,
      }));
    } catch (err) {
      console.error('Failed to cancel solve:', err);
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
      <div className="h-full flex items-center justify-center bg-bg terminal-noise">
        <div className="text-center animate-fade-in">
          <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-bg-tertiary border border-border flex items-center justify-center">
            <svg className="w-8 h-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <p className="text-fg-secondary font-mono text-lg mb-2">No repository selected</p>
          <p className="text-sm text-muted font-mono">Please select a repository to view issues</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-bg terminal-noise">
      {/* Header */}
      <div className="border-b border-border bg-[linear-gradient(120deg,rgba(245,158,11,0.12)_0%,rgba(34,211,238,0.05)_40%,rgba(10,10,11,0.9)_100%)]">
        <div className="p-6 space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-cyan font-mono mb-2">Solve Console</p>
              <h1 className="text-2xl font-mono font-semibold text-fg mb-1">Solve Issues</h1>
              <p className="text-sm text-fg-secondary font-mono">
                Prioritize one issue, launch solve runs, and compare outcomes from a single control surface.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1.5 rounded-lg border border-border bg-bg-secondary text-fg font-mono text-xs">
                Total {issues.length}
              </span>
              <span className="px-3 py-1.5 rounded-lg border border-amber/30 bg-amber/10 text-amber font-mono text-xs">
                Yudai {totalYudaiIssues}
              </span>
              <span className="px-3 py-1.5 rounded-lg border border-cyan/30 bg-cyan/10 text-cyan font-mono text-xs">
                Other {totalOtherIssues}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setViewState((prev) => ({ ...prev, filterYudai: 'all' }))}
            className={`px-4 py-2.5 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'all'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            All Issues ({issues.length})
          </button>
          <button
            onClick={() => setViewState((prev) => ({ ...prev, filterYudai: 'yudai' }))}
            className={`px-4 py-2.5 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'yudai'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            Yudai Generated ({totalYudaiIssues})
          </button>
          <button
            onClick={() => setViewState((prev) => ({ ...prev, filterYudai: 'others' }))}
            className={`px-4 py-2.5 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'others'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            Other Issues ({totalOtherIssues})
          </button>
        </div>
      </div>
      </div>

      {/* Issues Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="mb-4 p-4 bg-error/10 border border-error/30 rounded-xl animate-fade-in">
            <p className="text-error font-mono text-sm">{error}</p>
          </div>
        )}

        {isLoading && issues.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin h-10 w-10 border-3 border-amber border-t-transparent rounded-full" />
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-muted font-mono">No issues found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredIssues.map((issue, index) => (
              <button
                type="button"
                key={issue.number}
                onClick={() => setSolveUiState((prev) => ({ ...prev, selectedIssue: issue }))}
                className="bg-bg-secondary border border-border rounded-xl p-4 cursor-pointer hover:border-amber/40 hover:shadow-terminal transition-all duration-200 animate-fade-in group text-left"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-muted">#{issue.number}</span>
                    <span className="px-2 py-0.5 rounded-md border border-border bg-bg-tertiary text-[11px] uppercase tracking-wide text-fg-secondary font-mono">
                      {issue.state}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {issue.labels.includes('chat-generated') && (
                      <span className="px-2 py-0.5 bg-amber/10 text-amber border border-amber/20 text-xs font-mono font-semibold rounded-lg">
                        Yudai
                      </span>
                    )}
                  </div>
                </div>

                <h3 className="font-mono font-semibold text-fg text-base leading-snug mb-2 line-clamp-2 group-hover:text-amber transition-colors">
                  {issue.title}
                </h3>

                <p className="text-xs text-fg-secondary font-mono line-clamp-3 mb-4 leading-relaxed">
                  {issue.body || 'No description'}
                </p>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  {issue.labels.slice(0, 3).map((label) => (
                    <span
                      key={label}
                      className="px-2 py-0.5 bg-bg-tertiary text-xs font-mono rounded-md border border-border text-fg-secondary"
                    >
                      {label}
                    </span>
                  ))}
                  {issue.labels.length > 3 && (
                    <span className="px-2 py-0.5 text-xs font-mono text-muted">
                      +{issue.labels.length - 3} more
                    </span>
                  )}
                </div>

                <div className="pt-3 border-t border-border/70 flex items-center justify-between text-xs font-mono">
                  <span className="text-fg-secondary">Opened {new Date(issue.created_at).toLocaleDateString()}</span>
                  <span className="text-cyan">{issue.comments} comments</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {selectedIssue && (
        <IssueModal
          issue={selectedIssue}
          onClose={() => setSolveUiState((prev) => ({ ...prev, selectedIssue: null }))}
          onStartSolve={handleStartSolve}
          availableModels={availableModels}
          isLoading={isLoading}
        />
      )}

      {solveStatus && activeSolveId && activeSessionId && (
        <SolveProgressModal
          solveStatus={solveStatus}
          sessionId={activeSessionId}
          onClose={() => {
            setSolveUiState((prev) => ({
              ...prev,
              activeSolveId: null,
              solveStatus: null,
            }));
          }}
          onCancel={handleCancelSolve}
        />
      )}
    </div>
  );
}
