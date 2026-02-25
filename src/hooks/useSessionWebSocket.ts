import { useState, useEffect, useCallback, useRef } from 'react';
import { buildUnifiedSessionWebSocketUrl } from '../utils/realtimeRouting';
import { useAuthStore } from '../stores/authStore';
import type {
  TrajectoryData,
  ToolCallInfo,
  AgentQuestionInfo,
  WSEnvelope,
} from '../types/sessionTypes';

type WSStatus = 'idle' | 'connecting' | 'connected' | 'streaming' | 'completed' | 'error';

interface UseSessionWebSocketParams {
  sessionId: string;
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
  sendUserResponse: (questionId: string, answer: string) => void;
  disconnect: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_TIMEOUT_MS = 10_000;

export function useSessionWebSocket({
  sessionId,
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

  const connect = useCallback(() => {
    if (!sessionToken || !sessionId) return;

    const wsUrl = buildUnifiedSessionWebSocketUrl({
      sessionId,
      sessionToken,
    });

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
          const s = (envelope.payload as { status?: string }).status;
          if (s === 'connected') setStatus('connected');
          if (s === 'completed') setStatus('completed');
          break;
        }

        case 'heartbeat':
          // Timer already reset above
          break;

        case 'trajectory_update': {
          setStatus('streaming');
          const payload = envelope.payload as {
            messages: Array<{ role: string; content: string; extra?: Record<string, unknown> }>;
            info: Record<string, unknown>;
            message_count: number;
          };

          setTrajectory((prev) => {
            if (!prev) {
              return {
                info: payload.info as TrajectoryData['info'],
                messages: payload.messages,
              };
            }
            return {
              info: payload.info as TrajectoryData['info'],
              messages: [...prev.messages, ...payload.messages],
            };
          });
          setMessageCount(payload.message_count);
          break;
        }

        case 'tool_call': {
          const tc = envelope.payload as ToolCallInfo;
          setToolCalls((prev) => [...prev, tc]);
          break;
        }

        case 'agent_question': {
          const aq = envelope.payload as AgentQuestionInfo;
          setAgentQuestion(aq);
          break;
        }

        case 'error': {
          const msg = (envelope.payload as { message?: string }).message || 'Unknown error';
          setError(msg);
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
  }, [sessionToken, sessionId, cleanup, resetHeartbeatTimer, status]);

  useEffect(() => {
    if (enabled) {
      reconnectAttemptsRef.current = 0;
      connect();
    } else {
      cleanup();
      setStatus('idle');
    }
    return cleanup;
  }, [enabled, sessionId, sessionToken]); // eslint-disable-line react-hooks/exhaustive-deps

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
    (questionId: string, answer: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'user_response',
            payload: { question_id: questionId, answer },
          })
        );
      }
      setAgentQuestion(null);
    },
    []
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
