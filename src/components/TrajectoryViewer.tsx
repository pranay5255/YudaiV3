import React, { useEffect, useMemo, useState } from 'react';
import {
  FileText,
  ChevronRight,
  ChevronDown,
  DollarSign,
  MessageSquare,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import trajectoryData from '../data/last_mini_run.traj.json';
import { useAuthStore } from '../stores/authStore';
import type {
  SolveRunOut,
  SolveTrajectoryPayload,
  SolveTrajectoryResponse,
} from '../types/sessionTypes';

const apiCall = async <T,>(url: string): Promise<T> => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = useAuthStore.getState().sessionToken;
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(errorData.detail || errorData.message || 'Request failed');
  }

  return response.json() as Promise<T>;
};

const normalizeTrajectory = (payload: unknown): SolveTrajectoryPayload => {
  if (!payload || typeof payload !== 'object') {
    return { info: {}, messages: [] };
  }

  const candidate = payload as Partial<SolveTrajectoryPayload>;
  const info = candidate.info && typeof candidate.info === 'object' ? candidate.info : {};
  const messages = Array.isArray(candidate.messages)
    ? candidate.messages
        .filter((entry) => entry && typeof entry === 'object')
        .map((entry) => ({
          role: String(entry.role || 'assistant'),
          content: String(entry.content || ''),
        }))
    : [];

  return { info, messages };
};

const truncateContent = (content: string, maxLength = 150): string => {
  if (content.length <= maxLength) return content;
  return `${content.substring(0, maxLength)}...`;
};

const formatCost = (cost?: number): string => {
  return `$${(cost ?? 0).toFixed(4)}`;
};

const getStatusColorClass = (status?: string): string => {
  switch ((status || '').toLowerCase()) {
    case 'completed':
      return 'text-success';
    case 'running':
      return 'text-cyan';
    case 'failed':
      return 'text-error';
    case 'cancelled':
      return 'text-amber';
    default:
      return 'text-muted';
  }
};

interface TrajectoryViewerProps {
  sessionId?: string;
  solveId?: string;
  runs?: SolveRunOut[];
  pollIntervalMs?: number;
}

export const TrajectoryViewer: React.FC<TrajectoryViewerProps> = ({
  sessionId,
  solveId,
  runs,
  pollIntervalMs = 2000,
}) => {
  const [staticTrajectory, setStaticTrajectory] = useState<SolveTrajectoryPayload | null>(null);
  const [snapshots, setSnapshots] = useState<Record<string, SolveTrajectoryResponse>>({});
  const [loading, setLoading] = useState(true);
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const liveMode = Boolean(sessionId && solveId && runs && runs.length > 0);
  const runList = useMemo(() => runs ?? [], [runs]);

  useEffect(() => {
    if (!liveMode) {
      setSelectedRunId(null);
      return;
    }

    const preferredRunId =
      runList.find((run) => run.status === 'running')?.id ??
      runList.find((run) => run.status === 'completed')?.id ??
      runList[0]?.id ??
      null;

    setSelectedRunId((current) => {
      if (current && runList.some((run) => run.id === current)) {
        return current;
      }
      return preferredRunId;
    });
  }, [liveMode, runList]);

  useEffect(() => {
    setExpandedMessages(new Set());
  }, [selectedRunId]);

  useEffect(() => {
    if (liveMode) {
      setStaticTrajectory(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      setStaticTrajectory(normalizeTrajectory(trajectoryData));
    } catch (err) {
      console.error('Failed to load trajectory:', err);
      setError(err instanceof Error ? err.message : 'Failed to load trajectory');
      setStaticTrajectory(null);
    } finally {
      setLoading(false);
    }
  }, [liveMode]);

  useEffect(() => {
    if (!liveMode || !sessionId || !solveId || runList.length === 0) {
      return;
    }

    let cancelled = false;

    const pollRunTrajectories = async () => {
      try {
        const results = await Promise.all(
          runList.map(async (run) => {
            try {
              return await apiCall<SolveTrajectoryResponse>(
                `/api/daifu/sessions/${sessionId}/solve/trajectory/${solveId}/${run.id}`
              );
            } catch (runError) {
              console.error(`Failed to fetch trajectory for run ${run.id}:`, runError);
              return null;
            }
          })
        );

        if (cancelled) return;

        setSnapshots((current) => {
          const next = { ...current };
          for (const result of results) {
            if (!result) continue;
            next[result.run_id] = {
              ...result,
              trajectory: normalizeTrajectory(result.trajectory),
            };
          }
          return next;
        });
        setError(null);
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : 'Failed to poll trajectory');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    setLoading(true);
    void pollRunTrajectories();

    const hasActiveRuns = runList.some((run) => run.status === 'pending' || run.status === 'running');
    const intervalId = hasActiveRuns ? window.setInterval(pollRunTrajectories, pollIntervalMs) : null;

    return () => {
      cancelled = true;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [liveMode, pollIntervalMs, runList, sessionId, solveId]);

  const selectedRun = useMemo(
    () => runList.find((run) => run.id === selectedRunId) || null,
    [runList, selectedRunId]
  );

  const selectedSnapshot = useMemo(() => {
    if (!selectedRunId) return null;
    return snapshots[selectedRunId] || null;
  }, [selectedRunId, snapshots]);

  const trajectory: SolveTrajectoryPayload | null = liveMode
    ? selectedSnapshot?.trajectory || null
    : staticTrajectory;

  const info = trajectory?.info || {};
  const messages = trajectory?.messages || [];
  const liveSource = selectedSnapshot?.source || 'none';
  const liveStatus = selectedSnapshot?.run_status || selectedRun?.status || 'pending';

  const getStatusIcon = (statusText?: string) => {
    const status = (statusText || '').toLowerCase();
    if (status.includes('submit') || status.includes('complete') || status === 'completed') {
      return <CheckCircle className="w-5 h-5 text-success" />;
    }
    if (status.includes('fail') || status.includes('error') || status === 'failed') {
      return <XCircle className="w-5 h-5 text-error" />;
    }
    return <AlertCircle className="w-5 h-5 text-amber" />;
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-amber border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-fg/60 font-mono text-sm">Loading trajectory...</p>
        </div>
      </div>
    );
  }

  if (!trajectory) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-fg/60">
          <FileText className="w-12 h-12 mx-auto mb-4" />
          <p className="text-lg font-mono mb-2">No trajectory data available</p>
          {error && <p className="text-sm text-error font-mono">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-bg-secondary">
      <div className="p-4 border-b border-border bg-bg-tertiary">
        {liveMode && runList.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {runList.map((run) => {
              const snapshot = snapshots[run.id];
              const isSelected = run.id === selectedRunId;
              const messageCount = snapshot?.message_count ?? 0;
              const strategyName = run.evolution || 'balanced';

              return (
                <button
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  className={`px-3 py-2 rounded-lg border font-mono text-xs transition-colors ${
                    isSelected
                      ? 'border-amber/50 bg-amber/10 text-amber'
                      : 'border-border bg-bg-secondary text-fg-secondary hover:border-border-accent'
                  }`}
                >
                  <span className="block font-semibold">{strategyName}</span>
                  <span className={`block ${getStatusColorClass(run.status)}`}>{run.status.toUpperCase()} · {messageCount} msgs</span>
                </button>
              );
            })}
          </div>
        )}

        <div className="flex items-center gap-3 mb-3">
          {getStatusIcon(String(info.exit_status || liveStatus))}
          <div>
            <h3 className="font-semibold text-fg font-mono text-sm">
              {liveMode ? 'Arena Trajectory Stream' : 'Agent Execution Trajectory'}
            </h3>
            <p className="text-xs text-fg/60 font-mono">
              {info.config?.model?.model_name || selectedRun?.model || 'Unknown Model'}
              {info.mini_version ? ` • v${info.mini_version}` : ''}
              {liveMode ? ` • source:${liveSource}` : ''}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-bg-secondary border border-border rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1 font-mono">
              <DollarSign className="w-3 h-3" />
              <span>Cost</span>
            </div>
            <p className="text-lg font-semibold text-fg font-mono">
              {formatCost(info.model_stats?.instance_cost)}
            </p>
          </div>

          <div className="bg-bg-secondary border border-border rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1 font-mono">
              <MessageSquare className="w-3 h-3" />
              <span>API Calls</span>
            </div>
            <p className="text-lg font-semibold text-fg font-mono">
              {info.model_stats?.api_calls || 0}
            </p>
          </div>

          <div className="bg-bg-secondary border border-border rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1 font-mono">
              <Clock className="w-3 h-3" />
              <span>Messages</span>
            </div>
            <p className="text-lg font-semibold text-fg font-mono">{messages.length}</p>
          </div>

          <div className="bg-bg-secondary border border-border rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1 font-mono">
              <FileText className="w-3 h-3" />
              <span>Status</span>
            </div>
            <p className={`text-sm font-medium font-mono ${getStatusColorClass(String(info.exit_status || liveStatus))}`}>
              {String(info.exit_status || liveStatus || 'unknown')}
            </p>
          </div>
        </div>

        {info.submission && (
          <div className="mt-3 p-3 bg-success/10 border border-success/30 rounded-lg">
            <p className="text-xs text-success/80 font-medium mb-1 font-mono">Submission</p>
            <p className="text-sm text-fg font-mono">{info.submission}</p>
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 bg-error/10 border border-error/30 rounded-lg">
            <p className="text-xs text-error font-mono">{error}</p>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {messages.map((message, index) => {
            const isExpanded = expandedMessages.has(index);
            const isSystem = message.role === 'system';
            const isUser = message.role === 'user';
            const isAssistant = message.role === 'assistant';

            return (
              <div
                key={`${message.role}-${index}`}
                className={`
                  border rounded-lg transition-colors
                  ${isSystem ? 'bg-bg border-border' : ''}
                  ${isUser ? 'bg-cyan/5 border-cyan/30' : ''}
                  ${isAssistant ? 'bg-amber/5 border-amber/30' : ''}
                `}
              >
                <button
                  onClick={() => {
                    setExpandedMessages((current) => {
                      const next = new Set(current);
                      if (next.has(index)) {
                        next.delete(index);
                      } else {
                        next.add(index);
                      }
                      return next;
                    });
                  }}
                  className="w-full p-3 flex items-start gap-3 hover:bg-bg-tertiary transition-colors"
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-fg/60" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-fg/60" />
                    )}
                  </div>

                  <div className="flex-1 text-left min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`
                          text-xs font-medium px-2 py-0.5 rounded font-mono
                          ${isSystem ? 'bg-bg-tertiary text-fg-secondary' : ''}
                          ${isUser ? 'bg-cyan/20 text-cyan' : ''}
                          ${isAssistant ? 'bg-amber/20 text-amber' : ''}
                        `}
                      >
                        {message.role}
                      </span>
                      <span className="text-xs text-fg/40 font-mono">
                        Message {index + 1} of {messages.length}
                      </span>
                    </div>

                    <p className="text-sm text-fg/80 font-mono leading-relaxed whitespace-pre-wrap">
                      {isExpanded ? message.content : truncateContent(message.content, 200)}
                    </p>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
