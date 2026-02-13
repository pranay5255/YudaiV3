import React, { useState, useEffect, useRef } from 'react';
import { FileText, ChevronRight, ChevronDown, DollarSign, MessageSquare, Clock, CheckCircle, XCircle, AlertCircle, Radio } from 'lucide-react';
import { useTrajectoryStream } from '../hooks/useTrajectoryStream';
import type { TrajectoryData } from '../types/sessionTypes';
import trajectoryData from '../data/last_mini_run.traj.json';

interface TrajectoryViewerProps {
  // Static mode props
  staticData?: TrajectoryData;

  // Live streaming mode props
  isLive?: boolean;
  sessionId?: string;
  solveId?: string;
  runId?: string;
}

export const TrajectoryViewer: React.FC<TrajectoryViewerProps> = ({
  staticData,
  isLive = false,
  sessionId = '',
  solveId = '',
  runId = '',
}) => {
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Live streaming hook
  const {
    trajectory: liveTrajectory,
    streamStatus,
    error: streamError,
    messageCount: liveMessageCount,
  } = useTrajectoryStream({
    sessionId,
    solveId,
    runId,
    enabled: isLive,
  });

  // Static fallback data
  const [staticTrajectory, setStaticTrajectory] = useState<TrajectoryData | null>(null);
  const [loading, setLoading] = useState(!isLive);
  const [error, setError] = useState<string | null>(null);

  // Load static data if not in live mode
  useEffect(() => {
    if (isLive) return;

    const loadStatic = async () => {
      setLoading(true);
      setError(null);

      try {
        if (staticData) {
          setStaticTrajectory(staticData);
        } else {
          // Fallback to imported JSON
          setStaticTrajectory(trajectoryData as TrajectoryData);
        }
      } catch (err) {
        console.error('Failed to load trajectory:', err);
        setError(err instanceof Error ? err.message : 'Failed to load trajectory');
      } finally {
        setLoading(false);
      }
    };

    loadStatic();
  }, [isLive, staticData]);

  // Auto-scroll to latest message in live mode
  useEffect(() => {
    if (isLive && liveTrajectory && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isLive, liveMessageCount]);

  // Select data source based on mode
  const trajectory = isLive ? liveTrajectory : staticTrajectory;
  const currentError = isLive ? streamError : error;
  const isLoading = isLive ? streamStatus === 'connecting' : loading;

  const toggleMessage = (index: number) => {
    const newExpanded = new Set(expandedMessages);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedMessages(newExpanded);
  };

  const getStatusIcon = (exitStatus: string) => {
    const status = exitStatus?.toLowerCase() || '';
    if (status.includes('submit') || status.includes('complete')) {
      return <CheckCircle className="w-5 h-5 text-success" />;
    } else if (status.includes('fail') || status.includes('error')) {
      return <XCircle className="w-5 h-5 text-error" />;
    } else {
      return <AlertCircle className="w-5 h-5 text-amber" />;
    }
  };

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(4)}`;
  };

  const truncateContent = (content: string, maxLength: number = 150) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength) + '...';
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-fg/60">Loading trajectory...</p>
        </div>
      </div>
    );
  }

  if (currentError) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-error">
          <XCircle className="w-12 h-12 mx-auto mb-4" />
          <p className="text-lg font-semibold mb-2">Failed to Load Trajectory</p>
          <p className="text-sm text-fg/60">{currentError}</p>
        </div>
      </div>
    );
  }

  if (!trajectory) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-fg/60">
          <FileText className="w-12 h-12 mx-auto mb-4" />
          <p className="text-lg">No trajectory data available</p>
        </div>
      </div>
    );
  }

  const { info, messages } = trajectory;

  return (
    <div className="h-full flex flex-col">
      {/* Header - Trajectory Info */}
      <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-3 mb-3">
          {getStatusIcon(info.exit_status || '')}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-fg">Agent Execution Trajectory</h3>
              {isLive && streamStatus === 'streaming' && (
                <div className="flex items-center gap-1.5 px-2 py-1 bg-success/10 border border-success/30 rounded-lg">
                  <Radio className="w-3 h-3 text-success animate-pulse" />
                  <span className="text-xs font-medium text-success">LIVE</span>
                </div>
              )}
            </div>
            <p className="text-xs text-fg/60">
              {info.config?.model?.model_name || 'Unknown Model'} • v{info.mini_version || 'N/A'}
            </p>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1">
              <DollarSign className="w-3 h-3" />
              <span>Cost</span>
            </div>
            <p className="text-lg font-semibold text-fg">
              {formatCost(info.model_stats?.instance_cost || 0)}
            </p>
          </div>

          <div className="bg-zinc-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1">
              <MessageSquare className="w-3 h-3" />
              <span>API Calls</span>
            </div>
            <p className="text-lg font-semibold text-fg">
              {info.model_stats?.api_calls || 0}
            </p>
          </div>

          <div className="bg-zinc-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1">
              <Clock className="w-3 h-3" />
              <span>Messages</span>
            </div>
            <p className="text-lg font-semibold text-fg">
              {messages?.length || 0}
            </p>
          </div>

          <div className="bg-zinc-800/50 rounded-lg p-3">
            <div className="flex items-center gap-2 text-fg/60 text-xs mb-1">
              <FileText className="w-3 h-3" />
              <span>Status</span>
            </div>
            <p className="text-sm font-medium text-fg">
              {info.exit_status || 'Unknown'}
            </p>
          </div>
        </div>

        {info.submission && (
          <div className="mt-3 p-3 bg-success/10 border border-success/30 rounded-lg">
            <p className="text-xs text-success/80 font-medium mb-1">Submission</p>
            <p className="text-sm text-fg">{info.submission}</p>
          </div>
        )}
      </div>

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {messages.map((message, index) => {
            const isExpanded = expandedMessages.has(index);
            const isSystem = message.role === 'system';
            const isUser = message.role === 'user';
            const isAssistant = message.role === 'assistant';

            return (
              <div
                key={index}
                className={`
                  border rounded-lg transition-colors
                  ${isSystem ? 'bg-zinc-800/30 border-zinc-700/50' : ''}
                  ${isUser ? 'bg-primary/5 border-primary/20' : ''}
                  ${isAssistant ? 'bg-success/5 border-success/20' : ''}
                `}
              >
                <button
                  onClick={() => toggleMessage(index)}
                  className="w-full p-3 flex items-start gap-3 hover:bg-zinc-800/50 transition-colors"
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
                          text-xs font-medium px-2 py-0.5 rounded
                          ${isSystem ? 'bg-zinc-700 text-zinc-300' : ''}
                          ${isUser ? 'bg-primary/20 text-primary' : ''}
                          ${isAssistant ? 'bg-success/20 text-success' : ''}
                        `}
                      >
                        {message.role}
                      </span>
                      <span className="text-xs text-fg/40">
                        Message {index + 1} of {messages.length}
                      </span>
                    </div>

                    <p className="text-sm text-fg/80 font-mono leading-relaxed whitespace-pre-wrap">
                      {isExpanded
                        ? message.content
                        : truncateContent(message.content, 200)}
                    </p>
                  </div>
                </button>
              </div>
            );
          })}
          {/* Auto-scroll anchor for live mode */}
          {isLive && <div ref={messagesEndRef} />}
        </div>
      </div>
    </div>
  );
};
