import { useState, useEffect } from 'react';
import { useRepository } from '../hooks/useRepository';
import { useSessionManagement } from '../hooks/useSessionManagement';
import { useAuthStore } from '../stores/authStore';
import { logger } from '../utils/logger';
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
  const [selectedModelId, setSelectedModelId] = useState<number>(availableModels[0]?.id || 0);
  const [smallChange, setSmallChange] = useState(false);
  const [bestEffort, setBestEffort] = useState(false);

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
              <label className="block text-xs font-mono uppercase tracking-wider text-muted mb-2">
                Select AI Model
              </label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(Number(e.target.value))}
                className="w-full bg-bg-tertiary border border-border rounded-lg px-4 py-3 text-fg font-mono text-sm focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/10 transition-all duration-200"
                disabled={isLoading}
              >
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
              {availableModels.find(m => m.id === selectedModelId)?.description && (
                <p className="text-xs text-muted font-mono mt-2">
                  {availableModels.find(m => m.id === selectedModelId)?.description}
                </p>
              )}
            </div>

            {/* Options Checkboxes */}
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer p-3 bg-bg-tertiary border border-border rounded-lg hover:border-border-accent transition-colors">
                <input
                  type="checkbox"
                  checked={smallChange}
                  onChange={(e) => setSmallChange(e.target.checked)}
                  className="w-4 h-4 text-amber bg-bg border-border rounded focus:ring-amber accent-amber"
                  disabled={isLoading}
                />
                <div>
                  <span className="text-fg font-mono text-sm font-medium">Small Change</span>
                  <p className="text-xs text-muted font-mono">Limit scope to minimal code changes</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer p-3 bg-bg-tertiary border border-border rounded-lg hover:border-border-accent transition-colors">
                <input
                  type="checkbox"
                  checked={bestEffort}
                  onChange={(e) => setBestEffort(e.target.checked)}
                  className="w-4 h-4 text-amber bg-bg border-border rounded focus:ring-amber accent-amber"
                  disabled={isLoading}
                />
                <div>
                  <span className="text-fg font-mono text-sm font-medium">Best Effort</span>
                  <p className="text-xs text-muted font-mono">Continue solving even if tests fail</p>
                </div>
              </label>
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
            onClick={() => issue.id && onStartSolve(issue.id, selectedModelId, smallChange, bestEffort)}
            className="px-6 py-2.5 bg-amber hover:bg-amber/90 text-bg-primary rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed glow-amber flex items-center gap-2"
            disabled={isLoading || !selectedModelId || !issue.id}
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
  onClose: () => void;
  onCancel: () => void;
}

function SolveProgressModal({ solveStatus, onClose, onCancel }: SolveProgressModalProps) {
  const isComplete = isCompleteStatus(solveStatus.status);
  const canCancel = canCancelStatus(solveStatus.status);

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
  const { activeSessionId } = useSessionManagement();

  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [availableModels, setAvailableModels] = useState<AIModel[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<GitHubIssue | null>(null);
  const [activeSolveId, setActiveSolveId] = useState<string | null>(null);
  const [solveStatus, setSolveStatus] = useState<SolveStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterYudai, setFilterYudai] = useState<'all' | 'yudai' | 'others'>('all');

  // Fetch GitHub issues
  useEffect(() => {
    if (!selectedRepository) return;

    const fetchIssues = async () => {
      try {
        setIsLoading(true);
        setError(null);
        // Extract owner correctly - owner is an object, need to use .login or fallback to full_name
        const repoOwner = selectedRepository.repository.owner?.login ||
                          selectedRepository.repository.full_name.split('/')[0];
        const repoName = selectedRepository.repository.name;
        const data = await apiCall(
          `/api/daifu/github/repositories/${repoOwner}/${repoName}/issues`
        );
        setIssues(data);
      } catch (err) {
        logger.error('[SolveIssues] Failed to fetch issues:', err);
        const error = err as Error;
        setError(error.message || 'Failed to fetch issues');
      } finally {
        setIsLoading(false);
      }
    };

    fetchIssues();
  }, [selectedRepository]);

  // Fetch available AI models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const data = await apiCall('/api/daifu/ai-models');
        setAvailableModels(data);
      } catch (err) {
        logger.error('[SolveIssues] Failed to fetch AI models:', err);
      }
    };

    fetchModels();
  }, []);

  // Poll solve status when active
  useEffect(() => {
    if (!activeSolveId || !activeSessionId) return;

    const pollStatus = async () => {
      try {
        const data = await apiCall(
          `/api/daifu/sessions/${activeSessionId}/solve/status/${activeSolveId}`
        );
        setSolveStatus(data);

        // Stop polling if solve is complete
        if (isCompleteStatus(data.status)) {
          setActiveSolveId(null);
        }
      } catch (err) {
        logger.error('[SolveIssues] Failed to fetch solve status:', err);
      }
    };

    pollStatus();
    const interval = setInterval(pollStatus, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [activeSolveId, activeSessionId]);

  const handleStartSolve = async (
    issueId: number,
    modelId: number,
    smallChange: boolean,
    bestEffort: boolean
  ) => {
    if (!activeSessionId || !selectedRepository) {
      setError('No active session or repository selected');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

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

      const data = await apiCall(`/api/daifu/sessions/${activeSessionId}/solve/start`, {
        method: 'POST',
        body: JSON.stringify(solverPayload),
      });

      const response = data as StartSolveResponse;
      setActiveSolveId(response.solve_session_id);
      setSolveStatus({
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
      });
      setSelectedIssue(null);
    } catch (err) {
      logger.error('[SolveIssues] Failed to start solve:', err);
      const error = err as Error;
      setError(error.message || 'Failed to start solve');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelSolve = async () => {
    if (!activeSolveId || !activeSessionId) return;

    try {
      await apiCall(
        `/api/daifu/sessions/${activeSessionId}/solve/cancel/${activeSolveId}`,
        {
          method: 'POST',
        }
      );
      setActiveSolveId(null);
      setSolveStatus(null);
    } catch (err) {
      logger.error('[SolveIssues] Failed to cancel solve:', err);
    }
  };

  const filteredIssues = issues.filter((issue) => {
    if (filterYudai === 'yudai') return issue.labels.includes('chat-generated');
    if (filterYudai === 'others') return !issue.labels.includes('chat-generated');
    return true;
  });

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
      <div className="border-b border-border p-6 bg-bg-secondary">
        <h1 className="text-xl font-mono font-semibold text-fg mb-2">Solve Issues</h1>
        <p className="text-sm text-muted font-mono mb-4">
          Select an issue to solve using AI-powered agents
        </p>

        {/* Filter buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setFilterYudai('all')}
            className={`px-4 py-2 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'all'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            All Issues ({issues.length})
          </button>
          <button
            onClick={() => setFilterYudai('yudai')}
            className={`px-4 py-2 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'yudai'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            Yudai Generated ({issues.filter((i) => i.labels.includes('chat-generated')).length})
          </button>
          <button
            onClick={() => setFilterYudai('others')}
            className={`px-4 py-2 rounded-lg font-mono text-sm transition-all duration-200 ${
              filterYudai === 'others'
                ? 'bg-amber text-bg-primary font-semibold glow-amber'
                : 'bg-bg-tertiary text-muted hover:text-fg border border-border'
            }`}
          >
            Other Issues ({issues.filter((i) => !i.labels.includes('chat-generated')).length})
          </button>
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIssues.map((issue, index) => (
              <div
                key={issue.number}
                onClick={() => setSelectedIssue(issue)}
                className="bg-bg-secondary border border-border rounded-xl p-4 cursor-pointer hover:border-amber/30 transition-all duration-200 animate-fade-in group"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs font-mono text-muted">#{issue.number}</span>
                  {issue.labels.includes('chat-generated') && (
                    <span className="px-2 py-0.5 bg-amber/10 text-amber border border-amber/20 text-xs font-mono font-semibold rounded-lg">
                      Yudai
                    </span>
                  )}
                </div>
                <h3 className="font-mono font-medium text-fg text-sm mb-2 line-clamp-2 group-hover:text-amber transition-colors">{issue.title}</h3>
                <p className="text-xs text-muted font-mono line-clamp-3 mb-3">
                  {issue.body || 'No description'}
                </p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {issue.labels.slice(0, 3).map((label) => (
                    <span
                      key={label}
                      className="px-2 py-0.5 bg-bg-tertiary text-xs font-mono rounded-lg border border-border"
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
                <div className="flex items-center justify-between text-xs text-muted font-mono">
                  <span>{new Date(issue.created_at).toLocaleDateString()}</span>
                  <span>{issue.comments} comments</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      {selectedIssue && (
        <IssueModal
          issue={selectedIssue}
          onClose={() => setSelectedIssue(null)}
          onStartSolve={handleStartSolve}
          availableModels={availableModels}
          isLoading={isLoading}
        />
      )}

      {solveStatus && activeSolveId && (
        <SolveProgressModal
          solveStatus={solveStatus}
          onClose={() => {
            setActiveSolveId(null);
            setSolveStatus(null);
          }}
          onCancel={handleCancelSolve}
        />
      )}
    </div>
  );
}
