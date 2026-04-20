import React, { useState, useEffect, useMemo, useRef } from 'react';
import { FileText, ChevronRight, ChevronDown, DollarSign, MessageSquare, Clock, CheckCircle, XCircle, AlertCircle, Radio, Wrench } from 'lucide-react';
import { useSessionWebSocket } from '../hooks/useSessionWebSocket';
import type { TrajectoryData, ToolCallInfo, AgentQuestionInfo } from '../types/sessionTypes';
import { UserQuestionPrompt } from './UserQuestionPrompt';

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

  const wsStream = useSessionWebSocket({
    sessionId,
    solveId,
    runId,
    enabled: isLive,
  });

  const liveTrajectory = wsStream.trajectory;
  const streamStatus = wsStream.status;
  const streamError = wsStream.error;
  const liveMessageCount = wsStream.messageCount;
  const toolCalls: ToolCallInfo[] = wsStream.toolCalls;
  const agentQuestion: AgentQuestionInfo | null = wsStream.agentQuestion;

  const [staticState, setStaticState] = useState<{
    trajectory: TrajectoryData | null;
    loading: boolean;
    error: string | null;
  }>({
    trajectory: null,
    loading: !isLive,
    error: null,
  });

  useEffect(() => {
    if (isLive) return;

    setStaticState({
      trajectory: staticData ?? null,
      loading: false,
      error: null,
    });
  }, [isLive, staticData]);

  // Auto-scroll to latest message in live mode
  useEffect(() => {
    if (isLive && liveTrajectory && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isLive, liveMessageCount, liveTrajectory]);

  // Select data source based on mode
  const trajectory = isLive ? liveTrajectory : staticState.trajectory;
  const currentError = isLive ? streamError : staticState.error;
  const isLoading = isLive ? streamStatus === 'connecting' : staticState.loading;
  const messagesWithKeys = useMemo(() => {
    const sourceMessages = trajectory?.messages ?? [];
    const counts = new Map<string, number>();

    return sourceMessages.map((message) => {
      const extra = message.extra as Record<string, unknown> | undefined;
      const explicitId = typeof extra?.id === 'string'
        ? extra.id
        : typeof extra?.message_id === 'string'
          ? extra.message_id
          : null;
      const baseKey = explicitId ?? `${message.role}:${message.content}`;
      const occurrence = counts.get(baseKey) ?? 0;
      counts.set(baseKey, occurrence + 1);

      return {
        key: `${baseKey}:${occurrence}`,
        message,
      };
    });
  }, [trajectory]);

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

      {/* Agent Question (WS mode only) */}
      {agentQuestion && (
        <UserQuestionPrompt
          question={agentQuestion}
          onSubmit={(selectedOptionIds, answerText) =>
            wsStream.sendUserResponse(agentQuestion.question_id, selectedOptionIds, answerText)
          }
        />
      )}

      {/* Recent Tool Calls (WS mode only) */}
      {toolCalls.length > 0 && (
        <div className="mx-4 mt-2 p-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Wrench className="w-4 h-4 text-fg/60" />
            <p className="text-xs font-medium text-fg/60">Recent Tool Calls ({toolCalls.length})</p>
          </div>
          <div className="space-y-1">
            {toolCalls.slice(-5).map((tc, i) => (
              <div key={i} className="text-xs text-fg/50 font-mono">
                {tc.tool_name}({Object.keys(tc.tool_input).join(', ')})
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages List */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {messagesWithKeys.map(({ message, key }, index) => {
            const isExpanded = expandedMessages.has(index);
            const isSystem = message.role === 'system';
            const isUser = message.role === 'user';
            const isAssistant = message.role === 'assistant';

            return (
              <div
                key={key}
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
