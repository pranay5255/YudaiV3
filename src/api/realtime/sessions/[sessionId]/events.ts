import {
  getBackendBaseUrl,
  getInternalMiddlewareSecret,
  getRequiredInternalSecretResponse,
  isAuthResult,
  requireAuthenticatedUser,
} from '../../../_lib/backend.js';

const encoder = new TextEncoder();

const getSessionIdFromPath = (request: Request): string | null => {
  const match = new URL(request.url).pathname.match(/\/sessions\/([^/]+)\/events$/);
  return match ? decodeURIComponent(match[1]) : null;
};

const toBackendWsUrl = (sessionId: string, userId: number): string => {
  const backend = new URL(getBackendBaseUrl());
  backend.protocol = backend.protocol === 'https:' ? 'wss:' : 'ws:';
  backend.pathname = `/controller/sessions/${encodeURIComponent(sessionId)}/ws/unified`;
  backend.search = new URLSearchParams({
    internal_secret: getInternalMiddlewareSecret(),
    internal_user_id: String(userId),
  }).toString();
  return backend.toString();
};

const writeSse = (
  controller: ReadableStreamDefaultController<Uint8Array>,
  data: unknown,
  event = 'message'
): void => {
  controller.enqueue(
    encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
  );
};

export default {
  async fetch(request: Request): Promise<Response> {
    const missingSecret = getRequiredInternalSecretResponse();
    if (missingSecret) {
      return missingSecret;
    }

    const sessionId = getSessionIdFromPath(request);
    if (!sessionId) {
      return new Response('Missing session id', { status: 400 });
    }

    const auth = await requireAuthenticatedUser(request);
    if (!isAuthResult(auth)) {
      return auth;
    }

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        let closed = false;
        const closeOnce = (): void => {
          if (closed) {
            return;
          }
          closed = true;
          controller.close();
        };

        const ws = new WebSocket(toBackendWsUrl(sessionId, auth.user.id));
        const heartbeat = setInterval(() => {
          if (!closed) {
            writeSse(controller, { type: 'heartbeat' }, 'heartbeat');
          }
        }, 10_000);

        const stop = (): void => {
          clearInterval(heartbeat);
          try {
            ws.close();
          } catch {
            // ignore close failures
          }
          closeOnce();
        };

        request.signal.addEventListener('abort', stop, { once: true });

        ws.onmessage = (event: MessageEvent) => {
          if (closed) {
            return;
          }
          try {
            const text = typeof event.data === 'string' ? event.data : String(event.data);
            writeSse(controller, JSON.parse(text));
          } catch {
            writeSse(controller, {
              type: 'error',
              payload: {
                code: 'REALTIME_BRIDGE_PARSE_ERROR',
                message: 'Failed to parse backend realtime event',
              },
            });
          }
        };

        ws.onerror = () => {
          if (!closed) {
            writeSse(controller, {
              type: 'error',
              payload: {
                code: 'REALTIME_BRIDGE_BACKEND_ERROR',
                message: 'Backend realtime connection failed',
              },
            });
          }
          stop();
        };

        ws.onclose = () => {
          stop();
        };
      },
    });

    return new Response(stream, {
      headers: {
        'cache-control': 'no-cache',
        connection: 'keep-alive',
        'content-type': 'text/event-stream; charset=utf-8',
        'x-accel-buffering': 'no',
      },
    });
  },
};
