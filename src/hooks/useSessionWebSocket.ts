import { useState, useEffect, useCallback, useRef } from 'react';
import { buildUnifiedSessionWebSocketUrl } from '../utils/realtimeRouting';
import { useAuthStore } from '../stores/authStore';
import { API, buildApiUrl } from '../config/api';
import type {
  TrajectoryData,
  ToolCallInfo,
  AgentQuestionInfo,
  WSEnvelope,
} from '../types/sessionTypes';

type WSStatus = 'idle' | 'connecting' | 'connected' | 'streaming' | 'completed' | 'error';

interface UseSessionWebSocketParams {
  sessionId: string;
  solveId?: string;
  runId?: string;
  enabled: boolean;
}

interface UseSessionWebSocketResult {
  trajectory: TrajectoryData | null;
  status: WSStatus;
  error: string | null;
  messageCount: number;
  toolCalls: ToolCallInfo[];
  agentQuestion: AgentQuestionInfo | null;
  sendChatMessage: (content: string) => void;
  sendUserResponse: (questionId: string, selectedOptionIds: string[], answerText?: string) => Promise<void>;
  disconnect: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_TIMEOUT_MS = 10_000;

const getWsBaseUrl = (): string | undefined => {
  const value = (import.meta.env.VITE_WS_BASE_URL || '').trim();
  return value || undefined;
};

export function useSessionWebSocket({
  sessionId,
  solveId,
  runId,
  enabled,
}: UseSessionWebSocketParams): UseSessionWebSocketResult {
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [status, setStatus] = useState<WSStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);
  const [toolCalls, setToolCalls] = useState<ToolCallInfo[]>([]);
  const [agentQuestion, setAgentQuestion] = useState<AgentQuestionInfo | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionToken = useAuthStore((state) => state.sessionToken);

  const matchesSolveTarget = useCallback(
    (payload: Record<string, unknown>, requireScopedPayload: boolean = false) => {
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
      // No message in 10s — force reconnect
      if (wsRef.current) {
        wsRef.current.close(4000, 'heartbeat_timeout');
      }
    }, HEARTBEAT_TIMEOUT_MS);
  }, []);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    cleanup();
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS; // prevent reconnect
    setStatus('idle');
  }, [cleanup]);

  useEffect(() => {
    setTrajectory(null);
    setMessageCount(0);
    setError(null);
    setToolCalls([]);
    setAgentQuestion(null);
  }, [runId, sessionId, solveId]);

  const connect = useCallback(() => {
    if (!sessionToken || !sessionId) return;

    const wsBaseUrl = getWsBaseUrl();
    const wsUrl = buildUnifiedSessionWebSocketUrl({
      sessionId,
      sessionToken,
      controllerWsBaseUrl: wsBaseUrl,
    });

    if (
      typeof window !== 'undefined' &&
      window.location.protocol === 'https:' &&
      wsUrl.startsWith('ws://')
    ) {
      // Browsers generally block insecure websocket connections from HTTPS pages.
      console.warn('[WebSocket] ws:// from an https:// page may be blocked by browser mixed-content policy');
    }

    setStatus('connecting');
    setError(null);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttemptsRef.current = 0;
      resetHeartbeatTimer();
    };

    ws.onmessage = (event) => {
      resetHeartbeatTimer();

      let envelope: WSEnvelope;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        return;
      }

      switch (envelope.type) {
        case 'status': {
          const payload = envelope.payload as Record<string, unknown>;
          const s = typeof payload.status === 'string' ? payload.status : undefined;
          if (!s) {
            break;
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
          // Timer already reset above
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
          const payload = envelope.payload as { text?: string };
          const text = payload.text || '';
          if (text) {
            setTrajectory((prev) => ({
              info: prev?.info || {},
              messages: [
                ...(prev?.messages || []),
                { role: 'assistant', content: text },
              ],
            }));
            setMessageCount((count) => count + 1);
          }
          break;
        }

        case 'sandbox_stream': {
          if (solveId || runId) {
            break;
          }
          setStatus('streaming');
          const payload = envelope.payload as { event?: string; data?: string; exit_code?: number };
          const content =
            payload.event === 'exit'
              ? `[sandbox] process exited (${payload.exit_code ?? 'unknown'})`
              : `[sandbox:${payload.event || 'event'}] ${payload.data || ''}`;
          setTrajectory((prev) => ({
            info: prev?.info || {},
            messages: [
              ...(prev?.messages || []),
              { role: 'system', content },
            ],
          }));
          setMessageCount((count) => count + 1);
          break;
        }

        case 'mode_event':
        case 'state_event': {
          if (solveId || runId) {
            break;
          }
          const payload = envelope.payload as { state?: string; mode?: string };
          if (payload.state === 'workflow_complete' || payload.mode === 'complete') {
            setStatus('completed');
          }
          break;
        }

        case 'tool_call': {
          const tc = envelope.payload as ToolCallInfo;
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
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (heartbeatTimerRef.current) {
        clearTimeout(heartbeatTimerRef.current);
      }

      if (
        reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS &&
        status !== 'completed'
      ) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30_000);
        reconnectAttemptsRef.current += 1;
        setStatus('connecting');
        reconnectTimerRef.current = setTimeout(connect, delay);
      } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setStatus('error');
        setError('Connection lost after 10 reconnect attempts.');
      }
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
  }, [
    cleanup,
    matchesSolveTarget,
    resetHeartbeatTimer,
    runId,
    sessionId,
    sessionToken,
    solveId,
    status,
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

  const sendChatMessage = useCallback(
    (content: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'chat_message',
            payload: { content },
          })
        );
      }
    },
    []
  );

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

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'user_response',
            payload: { question_id: questionId, selected_option_ids: selectedOptionIds, answer: answerText || '' },
          })
        );
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
    sendChatMessage,
    sendUserResponse,
    disconnect,
  };
}
