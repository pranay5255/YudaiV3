import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuthStore } from '../stores/authStore';
import { buildApiUrl, API } from '../config/api';
import type {
  TrajectoryData,
  TrajectoryUpdateEvent,
  TrajectoryStatusEvent,
  TrajectoryErrorEvent,
} from '../types/sessionTypes';

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error';

interface UseTrajectoryStreamParams {
  sessionId: string;
  solveId: string;
  runId: string;
  enabled: boolean;
}

interface UseTrajectoryStreamResult {
  trajectory: TrajectoryData | null;
  streamStatus: StreamStatus;
  error: string | null;
  messageCount: number;
  disconnect: () => void;
}

export function useTrajectoryStream({
  sessionId,
  solveId,
  runId,
  enabled,
}: UseTrajectoryStreamParams): UseTrajectoryStreamResult {
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const sessionToken = useAuthStore((state) => state.sessionToken);

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    closeStream();
    setStreamStatus('idle');
  }, [closeStream]);

  useEffect(() => {
    if (!enabled || !sessionToken) {
      closeStream();
      setStreamStatus('idle');
      return;
    }

    // Build SSE URL with token query parameter
    const streamUrl = buildApiUrl(API.SESSIONS.SOLVER.STREAM, {
      sessionId,
      solveId,
      runId,
    });
    const urlWithToken = `${streamUrl}?token=${encodeURIComponent(sessionToken)}`;

    setStreamStatus('connecting');
    setError(null);

    const eventSource = new EventSource(urlWithToken);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setStreamStatus('streaming');
    };

    eventSource.addEventListener('trajectory_update', (event) => {
      try {
        const data = JSON.parse(event.data) as TrajectoryUpdateEvent;

        setTrajectory((prev) => {
          if (!prev) {
            // First update - initialize trajectory
            return {
              info: data.info,
              messages: data.messages,
            };
          }

          // Append new messages
          return {
            info: data.info,
            messages: [...prev.messages, ...data.messages],
          };
        });

        setMessageCount(data.message_count);
      } catch (err) {
        console.error('Failed to parse trajectory_update event:', err);
      }
    });

    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data) as TrajectoryStatusEvent;
        if (data.status === 'completed') {
          setStreamStatus('completed');
        }
      } catch (err) {
        console.error('Failed to parse status event:', err);
      }
    });

    eventSource.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as TrajectoryErrorEvent;
        setError(data.message);
        setStreamStatus('error');
        closeStream();
      } catch {
        // EventSource error event (network issue, etc.)
        setError('Connection error');
        setStreamStatus('error');
        closeStream();
      }
    });

    eventSource.addEventListener('done', () => {
      setStreamStatus('completed');
      closeStream();
    });

    eventSource.addEventListener('heartbeat', () => {
      // Heartbeat - just keep connection alive
    });

    eventSource.onerror = () => {
      setStreamStatus('error');
      setError('Connection lost');
      closeStream();
    };

    // Cleanup on unmount
    return () => {
      closeStream();
    };
  }, [enabled, sessionId, solveId, runId, sessionToken, closeStream]);

  return {
    trajectory,
    streamStatus,
    error,
    messageCount,
    disconnect,
  };
}
