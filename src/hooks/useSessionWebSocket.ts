import { useState, useEffect, useCallback, useRef } from 'react';
import { buildRealtimeSessionEventsUrl } from '../utils/realtimeRouting';
import { useAuthStore } from '../stores/authStore';
import { API, buildApiUrl } from '../config/api';
import type {
  TrajectoryData,
  ToolCallInfo,
  AgentQuestionInfo,
  WSEnvelope,
} from '../types/sessionTypes';

type StreamStatus = 'idle' | 'connecting' | 'connected' | 'streaming' | 'completed' | 'error';

interface UseSessionWebSocketParams {
  sessionId: string;
  solveId?: string;
  runId?: string;
  enabled: boolean;
  onAssistantMessage?: (message: {
    executionId?: string;
    final: boolean;
    messageId?: string;
    mode?: string;
    text: string;
  }) => void;
}

interface UseSessionWebSocketResult {
  trajectory: TrajectoryData | null;
  status: StreamStatus;
  error: string | null;
  messageCount: number;
  toolCalls: ToolCallInfo[];
  agentQuestion: AgentQuestionInfo | null;
  isExploringCodebase: boolean;
  explorationDetail: string | null;
  sendUserResponse: (questionId: string, selectedOptionIds: string[], answerText?: string) => Promise<void>;
  disconnect: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_TIMEOUT_MS = 15_000;

const parseSseDataFrames = (buffer: string): { frames: string[]; remaining: string } => {
  const frames: string[] = [];
  let remaining = buffer;
  let separatorIndex = remaining.indexOf('\n\n');

  while (separatorIndex >= 0) {
    const frame = remaining.slice(0, separatorIndex);
    remaining = remaining.slice(separatorIndex + 2);
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
      .trim();

    if (data && data !== '[DONE]') {
      frames.push(data);
    }

    separatorIndex = remaining.indexOf('\n\n');
  }

  return { frames, remaining };
};

export function useSessionWebSocket({
  sessionId,
  solveId,
  runId,
  enabled,
  onAssistantMessage,
}: UseSessionWebSocketParams): UseSessionWebSocketResult {
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);
  const [toolCalls, setToolCalls] = useState<ToolCallInfo[]>([]);
  const [agentQuestion, setAgentQuestion] = useState<AgentQuestionInfo | null>(null);
  const [isExploringCodebase, setIsExploringCodebase] = useState(false);
  const [explorationDetail, setExplorationDetail] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const statusRef = useRef<StreamStatus>('idle');
  const shouldReconnectRef = useRef(false);
  const activeLlmMessageIdRef = useRef<string | null>(null);
  const activeSandboxMessageIdsRef = useRef<Record<string, string>>({});
  const onAssistantMessageRef = useRef(onAssistantMessage);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionToken = useAuthStore((state) => state.sessionToken);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    onAssistantMessageRef.current = onAssistantMessage;
  }, [onAssistantMessage]);

  const matchesSolveTarget = useCallback(
    (payload: Record<string, unknown>, requireScopedPayload = false) => {
      const payloadSolveId =
        typeof payload.solve_id === 'string' ? payload.solve_id : undefined;
      const payloadRunId =
        typeof payload.run_id === 'string' ? payload.run_id : undefined;

      if (!solveId && !runId) {
        return true;
      }

      if (requireScopedPayload && !payloadSolveId && !payloadRunId) {
        return false;
      }

      if (solveId && payloadSolveId && payloadSolveId !== solveId) {
        return false;
      }

      if (runId && payloadRunId && payloadRunId !== runId) {
        return false;
      }

      if (solveId && requireScopedPayload && !payloadSolveId) {
        return false;
      }

      if (runId && requireScopedPayload && !payloadRunId) {
        return false;
      }

      return true;
    },
    [runId, solveId]
  );

  const resetHeartbeatTimer = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = setTimeout(() => {
      abortControllerRef.current?.abort();
    }, HEARTBEAT_TIMEOUT_MS);
  }, []);

  const cleanup = useCallback(() => {
    shouldReconnectRef.current = false;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  }, []);

  const disconnect = useCallback(() => {
    cleanup();
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS;
    setStatus('idle');
  }, [cleanup]);

  useEffect(() => {
    setTrajectory(null);
    setMessageCount(0);
    setError(null);
    setToolCalls([]);
    setAgentQuestion(null);
    setIsExploringCodebase(false);
    setExplorationDetail(null);
    activeLlmMessageIdRef.current = null;
    activeSandboxMessageIdsRef.current = {};
  }, [runId, sessionId, solveId]);

  const handleEnvelope = useCallback((envelope: WSEnvelope) => {
    switch (envelope.type) {
      case 'status': {
        const payload = envelope.payload as Record<string, unknown>;
        const s = typeof payload.status === 'string' ? payload.status : undefined;
        if (!s) {
          break;
        }
        const detail = typeof payload.detail === 'string' ? payload.detail : null;
        if (s === 'exploring_codebase') {
          setIsExploringCodebase(true);
          setExplorationDetail(detail);
        }
        if (
          s === 'exploration_complete' ||
          s === 'exploration_failed' ||
          s === 'exploration_skipped'
        ) {
          setIsExploringCodebase(false);
          setExplorationDetail(detail);
        }
        const isSolveScopedStatus = ['running', 'completed', 'failed', 'cancelled'].includes(s);
        if (isSolveScopedStatus && !matchesSolveTarget(payload, true)) {
          break;
        }
        if (s === 'connected') setStatus('connected');
        if (s === 'running') setStatus('streaming');
        if (s === 'completed') setStatus('completed');
        if (s === 'failed') {
          setStatus('error');
          setError('Solve failed.');
        }
        if (s === 'cancelled') {
          setStatus('error');
          setError('Solve cancelled.');
        }
        break;
      }

      case 'heartbeat':
        break;

      case 'trajectory_update': {
        const payload = envelope.payload as Record<string, unknown>;
        if (!matchesSolveTarget(payload, true)) {
          break;
        }
        setStatus('streaming');
        const trajectoryPayload = envelope.payload as {
          messages: Array<{ role: string; content: string; extra?: Record<string, unknown> }>;
          info: Record<string, unknown>;
          message_count: number;
          new_message_start_index?: number;
        };

        setTrajectory((prev) => {
          const startIndex =
            typeof trajectoryPayload.new_message_start_index === 'number'
              ? trajectoryPayload.new_message_start_index
              : prev?.messages.length ?? 0;
          if (!prev) {
            return {
              info: trajectoryPayload.info as TrajectoryData['info'],
              messages: trajectoryPayload.messages,
            };
          }
          return {
            info: trajectoryPayload.info as TrajectoryData['info'],
            messages: [
              ...prev.messages.slice(0, Math.max(startIndex, 0)),
              ...trajectoryPayload.messages,
            ],
          };
        });
        setMessageCount(trajectoryPayload.message_count);
        break;
      }

      case 'llm_stream': {
        if (solveId || runId) {
          break;
        }
        setStatus('streaming');
        const payload = envelope.payload as {
          execution_id?: string;
          text?: string;
          final?: boolean;
          final_text?: string;
          message_id?: string;
          mode?: string;
        };
        const hasFinalText = typeof payload.final_text === 'string';
        const text = hasFinalText ? payload.final_text || '' : payload.text || '';
        const isNewMessage = !activeLlmMessageIdRef.current;

        if (text || payload.final) {
          const streamMessageId =
            activeLlmMessageIdRef.current ||
            payload.message_id ||
            `llm_stream_${Date.now()}`;
          activeLlmMessageIdRef.current = streamMessageId;

          setTrajectory((prev) => {
            const messages = [...(prev?.messages || [])];
            const existingIndex = messages.findIndex((message) => {
              const extra = message.extra || {};
              return (
                extra.stream_id === streamMessageId ||
                (payload.message_id && extra.message_id === payload.message_id)
              );
            });

            if (existingIndex >= 0) {
              const existing = messages[existingIndex];
              messages[existingIndex] = {
                ...existing,
                content: hasFinalText ? text : `${existing.content}${text}`,
                extra: {
                  ...(existing.extra || {}),
                  stream_id: streamMessageId,
                  message_id: payload.message_id || existing.extra?.message_id,
                  final: Boolean(payload.final),
                },
              };
            } else if (text) {
              messages.push({
                role: 'assistant',
                content: text,
                extra: {
                  stream_id: streamMessageId,
                  message_id: payload.message_id,
                  final: Boolean(payload.final),
                },
              });
            }

            return {
              info: prev?.info || {},
              messages,
            };
          });

          if (isNewMessage && text) {
            setMessageCount((count) => count + 1);
          }
        }

        if (payload.final) {
          const finalText = hasFinalText ? text : text.trim() ? text : '';
          if (finalText) {
            onAssistantMessageRef.current?.({
              executionId: typeof payload.execution_id === 'string' ? payload.execution_id : undefined,
              final: true,
              messageId: payload.message_id,
              mode: typeof payload.mode === 'string' ? payload.mode : undefined,
              text: finalText,
            });
          }
          activeLlmMessageIdRef.current = null;
        }
        break;
      }

      case 'sandbox_stream': {
        if (solveId || runId) {
          break;
        }
        setStatus('streaming');
        const payload = envelope.payload as {
          event?: string;
          stream?: string;
          data?: string;
          exit_code?: number;
          mode?: string;
          execution_id?: string;
          pipeline_execution_id?: string;
        };
        const eventName = payload.event || 'event';
        const modeName = payload.mode || 'sandbox';
        const streamName = payload.stream || eventName;
        const streamKey = [
          payload.pipeline_execution_id || 'pipeline',
          payload.execution_id || 'execution',
          modeName,
          streamName,
        ].join(':');
        const isNewSandboxMessage = !activeSandboxMessageIdsRef.current[streamKey];
        const existingStreamMessageId =
          activeSandboxMessageIdsRef.current[streamKey] ||
          `sandbox_stream_${streamKey}_${Date.now()}`;
        activeSandboxMessageIdsRef.current[streamKey] = existingStreamMessageId;

        const chunk =
          eventName === 'exit'
            ? `[${modeName}] sandbox process exited (${payload.exit_code ?? 'unknown'})`
            : `[${modeName}:${streamName}] ${payload.data || ''}`.trimEnd();

        setTrajectory((prev) => {
          const messages = [...(prev?.messages || [])];
          const existingIndex = messages.findIndex((message) => {
            const extra = message.extra || {};
            return extra.stream_id === existingStreamMessageId;
          });

          if (existingIndex >= 0) {
            const existing = messages[existingIndex];
            const separator =
              existing.content.endsWith('\n') || chunk.startsWith('\n') ? '' : '\n';
            messages[existingIndex] = {
              ...existing,
              content: `${existing.content}${separator}${chunk}`,
              extra: {
                ...(existing.extra || {}),
                stream_id: existingStreamMessageId,
                mode: modeName,
                stream: streamName,
                final: eventName === 'exit',
                exit_code: payload.exit_code,
              },
            };
            return {
              info: prev?.info || {},
              messages,
            };
          }

          messages.push({
            role: 'system',
            content: chunk,
            extra: {
              id: existingStreamMessageId,
              stream_id: existingStreamMessageId,
              mode: modeName,
              stream: streamName,
              final: eventName === 'exit',
              exit_code: payload.exit_code,
            },
          });

          return {
            info: prev?.info || {},
            messages,
          };
        });

        if (eventName === 'exit') {
          delete activeSandboxMessageIdsRef.current[streamKey];
        }
        if (isNewSandboxMessage) {
          setMessageCount((count) => count + 1);
        }
        break;
      }

      case 'mode_event':
      case 'state_event': {
        if (solveId || runId) {
          break;
        }
        const payload = envelope.payload as {
          state?: string;
          mode?: string;
          execution_id?: string;
          mode_execution_id?: string;
          detail?: string;
        };
        if (payload.state === 'workflow_complete' || payload.mode === 'complete') {
          setStatus('completed');
        }
        if (payload.mode || payload.state || payload.detail) {
          const modeName = payload.mode || 'workflow';
          const stateName = payload.state || 'event';
          const content = payload.detail || `[mode:${modeName}] ${stateName}`;
          setTrajectory((prev) => ({
            info: {
              ...(prev?.info || {}),
              exit_status:
                stateName === 'failed'
                  ? 'failed'
                  : stateName === 'workflow_complete' || modeName === 'complete'
                    ? 'complete'
                    : prev?.info?.exit_status,
            },
            messages: [
              ...(prev?.messages || []),
              {
                role: 'system',
                content,
                extra: {
                  id: `mode_event_${payload.execution_id || 'exec'}_${modeName}_${stateName}_${Date.now()}`,
                  mode: modeName,
                  state: stateName,
                  mode_execution_id: payload.mode_execution_id,
                },
              },
            ],
          }));
          setMessageCount((count) => count + 1);
        }
        break;
      }

      case 'tool_call': {
        const tc = envelope.payload as unknown as ToolCallInfo;
        setToolCalls((prev) => [...prev, tc]);
        break;
      }

      case 'agent_question': {
        const payload = envelope.payload as {
          question_id?: string;
          question_text?: string;
          multi_select?: boolean;
          options?: Array<string | { id?: string; label?: string }>;
          option_ids?: string[];
          question_metadata?: Record<string, unknown>;
        };
        const rawOptions = payload.options || [];
        const optionIds = payload.option_ids || [];
        const normalizedOptions = rawOptions
          .map((option, index) => {
            if (typeof option === 'string') {
              return {
                id: optionIds[index] || option.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
                label: option,
              };
            }
            const id = String(option?.id || optionIds[index] || `option-${index + 1}`).trim();
            const label = String(option?.label || '').trim();
            if (!id || !label) {
              return null;
            }
            return { id, label };
          })
          .filter((item): item is { id: string; label: string } => Boolean(item));

        setAgentQuestion({
          question_id: String(payload.question_id || ''),
          question_text: String(payload.question_text || ''),
          multi_select: Boolean(payload.multi_select),
          options: normalizedOptions,
          question_metadata: payload.question_metadata,
        });
        break;
      }

      case 'error': {
        const payload = envelope.payload as Record<string, unknown>;
        if (!matchesSolveTarget(payload, Boolean(solveId || runId))) {
          break;
        }
        const msg =
          typeof payload.message === 'string' ? payload.message : 'Unknown error';
        setError(msg);
        setStatus('error');
        break;
      }

      case 'done':
        setStatus('completed');
        cleanup();
        break;
    }
  }, [cleanup, matchesSolveTarget, runId, solveId]);

  const scheduleReconnect = useCallback((connect: () => void) => {
    if (
      shouldReconnectRef.current &&
      reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS &&
      statusRef.current !== 'completed'
    ) {
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30_000);
      reconnectAttemptsRef.current += 1;
      setStatus('connecting');
      reconnectTimerRef.current = setTimeout(connect, delay);
    } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setStatus('error');
      setError('Connection lost after 10 reconnect attempts.');
    }
  }, []);

  const connect = useCallback(() => {
    if (!sessionToken || !sessionId) return;

    shouldReconnectRef.current = true;
    setStatus('connecting');
    setError(null);

    const controller = new AbortController();
    abortControllerRef.current?.abort();
    abortControllerRef.current = controller;

    const run = async (): Promise<void> => {
      try {
        const response = await fetch(buildRealtimeSessionEventsUrl(sessionId), {
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Realtime stream failed with status ${response.status}`);
        }

        setStatus('connected');
        reconnectAttemptsRef.current = 0;
        resetHeartbeatTimer();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseDataFrames(buffer);
          buffer = parsed.remaining;

          parsed.frames.forEach((frame) => {
            resetHeartbeatTimer();
            try {
              handleEnvelope(JSON.parse(frame) as WSEnvelope);
            } catch {
              // Ignore malformed bridge events and keep the stream alive.
            }
          });
        }
      } catch (streamError) {
        if (!controller.signal.aborted) {
          const message = streamError instanceof Error
            ? streamError.message
            : 'Realtime stream failed.';
          console.error('[Realtime] Session event stream failed:', streamError);
          setError(message);
        }
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        if (heartbeatTimerRef.current) {
          clearTimeout(heartbeatTimerRef.current);
          heartbeatTimerRef.current = null;
        }
        if (!controller.signal.aborted && statusRef.current !== 'completed') {
          scheduleReconnect(connect);
        }
      }
    };

    void run();
  }, [
    handleEnvelope,
    resetHeartbeatTimer,
    scheduleReconnect,
    sessionId,
    sessionToken,
  ]);

  useEffect(() => {
    if (enabled) {
      reconnectAttemptsRef.current = 0;
      connect();
    } else {
      cleanup();
      setStatus('idle');
    }
    return cleanup;
  }, [cleanup, connect, enabled, runId, sessionId, sessionToken, solveId]);

  const sendUserResponse = useCallback(
    async (questionId: string, selectedOptionIds: string[], answerText?: string) => {
      if (!sessionToken || !sessionId) {
        throw new Error('Missing authenticated session context');
      }

      const endpoint = buildApiUrl(API.SESSIONS.ANSWER_QUESTION, {
        sessionId,
        questionId,
      });

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({
          selected_option_ids: selectedOptionIds,
          answer_text: answerText || undefined,
          resume_execution: true,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const message = String(data?.detail || data?.message || 'Failed to submit answer');
        setError(message);
        throw new Error(message);
      }

      setAgentQuestion(null);
    },
    [sessionToken, sessionId]
  );

  return {
    trajectory,
    status,
    error,
    messageCount,
    toolCalls,
    agentQuestion,
    isExploringCodebase,
    explorationDetail,
    sendUserResponse,
    disconnect,
  };
}
