import { useState, useEffect } from 'react';
import { useRepository } from '../hooks/useRepository';
import { useSessionManagement } from '../hooks/useSessionManagement';

// Simple API helper
const apiCall = async (url: string, options?: RequestInit) => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('session_token');
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

interface SolveProgress {
  runs_total: number;
  runs_completed: number;
  runs_failed: number;
  runs_running: number;
  last_update: string;
  message: string;
}

interface SolveRun {
  id: string;
  model: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  started_at?: string;
  completed_at?: string;
  pr_url?: string;
  error_message?: string;
}

interface SolveStatus {
  solve_session_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress: SolveProgress;
  runs: SolveRun[];
  champion_run?: SolveRun;
  error_message?: string;
}

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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-bg-secondary rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-bg-secondary border-b border-border p-6 flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold text-fg">
                #{issue.number} {issue.title}
              </h2>
              {isYudaiGenerated && (
                <span className="px-2 py-1 bg-accent text-accent-fg text-xs font-semibold rounded">
                  Yudai Generated
                </span>
              )}
            </div>
            <a
              href={issue.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted hover:text-fg"
            >
              View on GitHub →
            </a>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-fg p-2"
            disabled={isLoading}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Issue Description */}
          <div>
            <h3 className="text-sm font-semibold text-muted mb-2">Issue Description</h3>
            <div className="bg-bg p-4 rounded border border-border">
              <p className="text-fg whitespace-pre-wrap">{issue.body || 'No description provided'}</p>
            </div>
          </div>

          {/* Labels */}
          {issue.labels.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-muted mb-2">Labels</h3>
              <div className="flex flex-wrap gap-2">
                {issue.labels.map((label) => (
                  <span
                    key={label}
                    className="px-2 py-1 bg-bg text-fg text-xs rounded border border-border"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Solve Options */}
          <div className="space-y-4 pt-4 border-t border-border">
            <h3 className="text-lg font-semibold text-fg">Solve Configuration</h3>

            {/* AI Model Selection */}
            <div>
              <label className="block text-sm font-medium text-muted mb-2">
                Select AI Model
              </label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(Number(e.target.value))}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-fg focus:outline-none focus:ring-2 focus:ring-accent"
                disabled={isLoading}
              >
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
              {availableModels.find(m => m.id === selectedModelId)?.description && (
                <p className="text-xs text-muted mt-1">
                  {availableModels.find(m => m.id === selectedModelId)?.description}
                </p>
              )}
            </div>

            {/* Options Checkboxes */}
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={smallChange}
                  onChange={(e) => setSmallChange(e.target.checked)}
                  className="w-4 h-4 text-accent bg-bg border-border rounded focus:ring-accent"
                  disabled={isLoading}
                />
                <div>
                  <span className="text-fg font-medium">Small Change</span>
                  <p className="text-xs text-muted">Limit scope to minimal code changes</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={bestEffort}
                  onChange={(e) => setBestEffort(e.target.checked)}
                  className="w-4 h-4 text-accent bg-bg border-border rounded focus:ring-accent"
                  disabled={isLoading}
                />
                <div>
                  <span className="text-fg font-medium">Best Effort</span>
                  <p className="text-xs text-muted">Continue solving even if tests fail</p>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-bg-secondary border-t border-border p-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-bg text-fg rounded hover:bg-bg-secondary border border-border"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={() => issue.id && onStartSolve(issue.id, selectedModelId, smallChange, bestEffort)}
            className="px-6 py-2 bg-accent text-accent-fg rounded hover:bg-accent-hover font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isLoading || !selectedModelId || !issue.id}
          >
            {isLoading ? 'Starting Solve...' : 'Start Solve'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface SolveProgressModalProps {
  solveStatus: SolveStatus;
  onClose: () => void;
  onCancel: () => void;
}

function SolveProgressModal({ solveStatus, onClose, onCancel }: SolveProgressModalProps) {
  const isComplete = ['COMPLETED', 'FAILED', 'CANCELLED'].includes(solveStatus.status);
  const canCancel = ['PENDING', 'RUNNING'].includes(solveStatus.status);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-green-500';
      case 'RUNNING':
        return 'text-blue-500';
      case 'FAILED':
        return 'text-red-500';
      case 'CANCELLED':
        return 'text-yellow-500';
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-bg-secondary rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-bg-secondary border-b border-border p-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold text-fg">Solve Progress</h2>
            <button
              onClick={onClose}
              className="text-muted hover:text-fg p-2"
              disabled={!isComplete}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Progress Overview */}
        <div className="p-6 space-y-6">
          <div className="bg-bg p-4 rounded border border-border">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-fg">Overall Status</h3>
                <p className={`text-sm font-medium ${getStatusColor(solveStatus.status)}`}>
                  {solveStatus.status}
                </p>
              </div>
              {!isComplete && (
                <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
              )}
            </div>

            {/* Progress Stats */}
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-fg">{solveStatus.progress.runs_total}</p>
                <p className="text-xs text-muted">Total Runs</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-green-500">{solveStatus.progress.runs_completed}</p>
                <p className="text-xs text-muted">Completed</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-500">{solveStatus.progress.runs_running}</p>
                <p className="text-xs text-muted">Running</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-500">{solveStatus.progress.runs_failed}</p>
                <p className="text-xs text-muted">Failed</p>
              </div>
            </div>

            {solveStatus.error_message && (
              <div className="mt-4 p-3 bg-red-500 bg-opacity-10 border border-red-500 rounded">
                <p className="text-sm text-red-500">{solveStatus.error_message}</p>
              </div>
            )}
          </div>

          {/* Champion Run */}
          {solveStatus.champion_run && (
            <div className="bg-green-500 bg-opacity-10 border border-green-500 rounded p-4">
              <h3 className="text-lg font-semibold text-green-500 mb-2">🏆 Champion Solution</h3>
              <p className="text-fg mb-2">Model: {solveStatus.champion_run.model}</p>
              {solveStatus.champion_run.pr_url && (
                <a
                  href={solveStatus.champion_run.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:text-accent-hover underline"
                >
                  View Pull Request →
                </a>
              )}
            </div>
          )}

          {/* Individual Runs */}
          <div>
            <h3 className="text-lg font-semibold text-fg mb-3">Run Details</h3>
            <div className="space-y-3">
              {solveStatus.runs.map((run) => (
                <div
                  key={run.id}
                  className="bg-bg p-4 rounded border border-border"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className={`text-2xl ${getStatusColor(run.status)}`}>
                        {getStatusIcon(run.status)}
                      </span>
                      <div>
                        <p className="font-medium text-fg">{run.model}</p>
                        <p className={`text-sm ${getStatusColor(run.status)}`}>
                          {run.status}
                        </p>
                      </div>
                    </div>
                    {run.pr_url && (
                      <a
                        href={run.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-accent hover:text-accent-hover underline"
                      >
                        View PR
                      </a>
                    )}
                  </div>

                  {run.error_message && (
                    <p className="text-xs text-red-500 mt-2">{run.error_message}</p>
                  )}

                  <div className="flex gap-4 text-xs text-muted mt-2">
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
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 font-semibold"
            >
              Cancel Solve
            </button>
          )}
          {isComplete && (
            <button
              onClick={onClose}
              className="px-6 py-2 bg-accent text-accent-fg rounded hover:bg-accent-hover font-semibold"
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
  const [solveStatus, setSolveStatus] = useState<SolveStatus | null>(null);
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
        const data = await apiCall(
          `/api/daifu/github/repositories/${selectedRepository.repository.owner}/${selectedRepository.repository.name}/issues`
        );
        setIssues(data);
      } catch (err) {
        console.error('Failed to fetch issues:', err);
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
        console.error('Failed to fetch AI models:', err);
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
        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(data.status)) {
          setActiveSolveId(null);
        }
      } catch (err) {
        console.error('Failed to fetch solve status:', err);
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

      const data = await apiCall(
        `/api/daifu/sessions/${activeSessionId}/solve/start`,
        {
          method: 'POST',
          body: JSON.stringify({
            issue_id: issueId,
            ai_model_id: modelId,
            repo_url: `https://github.com/${selectedRepository.repository.owner}/${selectedRepository.repository.name}`,
            branch_name: selectedRepository.branch || 'main',
            small_change: smallChange,
            best_effort: bestEffort,
          }),
        }
      );

      setActiveSolveId(data.solve_session_id);
      setSolveStatus({
        solve_session_id: data.solve_session_id,
        status: data.status,
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
      console.error('Failed to start solve:', err);
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
      console.error('Failed to cancel solve:', err);
    }
  };

  const filteredIssues = issues.filter((issue) => {
    if (filterYudai === 'yudai') return issue.labels.includes('chat-generated');
    if (filterYudai === 'others') return !issue.labels.includes('chat-generated');
    return true;
  });

  if (!selectedRepository) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted text-lg mb-2">No repository selected</p>
          <p className="text-sm text-muted">Please select a repository to view issues</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-bg">
      {/* Header */}
      <div className="border-b border-border p-6">
        <h1 className="text-2xl font-bold text-fg mb-2">Solve Issues</h1>
        <p className="text-sm text-muted mb-4">
          Select an issue to solve using AI-powered agents
        </p>

        {/* Filter buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setFilterYudai('all')}
            className={`px-4 py-2 rounded ${
              filterYudai === 'all'
                ? 'bg-accent text-accent-fg'
                : 'bg-bg-secondary text-muted hover:bg-bg'
            }`}
          >
            All Issues ({issues.length})
          </button>
          <button
            onClick={() => setFilterYudai('yudai')}
            className={`px-4 py-2 rounded ${
              filterYudai === 'yudai'
                ? 'bg-accent text-accent-fg'
                : 'bg-bg-secondary text-muted hover:bg-bg'
            }`}
          >
            Yudai Generated ({issues.filter((i) => i.labels.includes('chat-generated')).length})
          </button>
          <button
            onClick={() => setFilterYudai('others')}
            className={`px-4 py-2 rounded ${
              filterYudai === 'others'
                ? 'bg-accent text-accent-fg'
                : 'bg-bg-secondary text-muted hover:bg-bg'
            }`}
          >
            Other Issues ({issues.filter((i) => !i.labels.includes('chat-generated')).length})
          </button>
        </div>
      </div>

      {/* Issues Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="mb-4 p-4 bg-red-500 bg-opacity-10 border border-red-500 rounded">
            <p className="text-red-500">{error}</p>
          </div>
        )}

        {isLoading && issues.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin h-12 w-12 border-4 border-accent border-t-transparent rounded-full" />
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-muted">No issues found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIssues.map((issue) => (
              <div
                key={issue.number}
                onClick={() => setSelectedIssue(issue)}
                className="bg-bg-secondary border border-border rounded-lg p-4 cursor-pointer hover:border-accent transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-sm font-mono text-muted">#{issue.number}</span>
                  {issue.labels.includes('chat-generated') && (
                    <span className="px-2 py-0.5 bg-accent text-accent-fg text-xs font-semibold rounded">
                      Yudai
                    </span>
                  )}
                </div>
                <h3 className="font-semibold text-fg mb-2 line-clamp-2">{issue.title}</h3>
                <p className="text-sm text-muted line-clamp-3 mb-3">
                  {issue.body || 'No description'}
                </p>
                <div className="flex flex-wrap gap-1 mb-2">
                  {issue.labels.slice(0, 3).map((label) => (
                    <span
                      key={label}
                      className="px-2 py-0.5 bg-bg text-xs rounded border border-border"
                    >
                      {label}
                    </span>
                  ))}
                  {issue.labels.length > 3 && (
                    <span className="px-2 py-0.5 text-xs text-muted">
                      +{issue.labels.length - 3} more
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-xs text-muted">
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

