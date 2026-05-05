import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import aiStreamHandler from '../../api/ai/sessions/[sessionId]/stream';
import proxyHandler from '../../api/proxy/[...path]';
import realtimeEventsHandler from '../../api/realtime/sessions/[sessionId]/events';

const originalEnv = { ...process.env };

type FetchCall = {
  input: RequestInfo | URL;
  init?: RequestInit;
};

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closed = false;
  url: string;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close(): void {
    // The bridge calls close during abort cleanup; tests do not need to echo
    // an onclose event back into the cleanup path.
    this.closed = true;
  }

  emitMessage(data: string): void {
    this.onmessage?.({ data } as MessageEvent);
  }
}

const setMiddlewareEnv = () => {
  process.env.YUDAI_BACKEND_BASE_URL = 'https://backend.test';
  process.env.YUDAI_INTERNAL_MIDDLEWARE_SECRET = 'internal-secret';
  delete process.env.OPENROUTER_API_KEY;
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });

describe('Vercel middleware handlers', () => {
  beforeEach(() => {
    process.env = { ...originalEnv };
    setMiddlewareEnv();
    FakeWebSocket.instances = [];
    vi.stubGlobal('fetch', vi.fn());
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('validates auth before proxying app API requests with internal headers', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({
        github_id: 'gh_1',
        github_username: 'tester',
        id: 7,
      }))
      .mockResolvedValueOnce(jsonResponse([{ full_name: 'octocat/yudaiv3' }]));

    const response = await proxyHandler.fetch(new Request(
      'https://yudai.app/api/proxy/github/repositories?limit=5',
      { headers: { authorization: 'Bearer session-token' } }
    ));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ full_name: 'octocat/yudaiv3' }]);

    const calls = fetchMock.mock.calls.map(([input, init]): FetchCall => ({ input, init }));
    expect(String(calls[0]?.input)).toBe('https://backend.test/auth/api/user');
    expect(String(calls[1]?.input)).toBe(
      'https://backend.test/github/repositories?limit=5'
    );

    const backendHeaders = new Headers(calls[1]?.init?.headers);
    expect(backendHeaders.get('x-yudai-internal-secret')).toBe('internal-secret');
    expect(backendHeaders.get('x-yudai-user-id')).toBe('7');
    expect(backendHeaders.has('authorization')).toBe(false);
  });

  it('streams AI SDK responses after auth and persists the turn through Python', async () => {
    let persistedTurn: Record<string, unknown> | null = null;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === 'https://backend.test/auth/api/user') {
        return jsonResponse({
          github_id: 'gh_1',
          github_username: 'tester',
          id: 7,
        });
      }
      if (url === 'https://backend.test/daifu/sessions/session_123/ai-context') {
        return jsonResponse({
          context_cards: [{ content: 'Use tests first', id: 1, title: 'Plan' }],
          messages: [],
          pending_questions: [],
          repository_info: { branch: 'main', name: 'yudaiv3', owner: 'octocat' },
          session: { session_id: 'session_123' },
        });
      }
      if (url === 'https://backend.test/daifu/sessions/session_123/ai-turns') {
        persistedTurn = JSON.parse(String(init?.body));
        return jsonResponse({ success: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    const response = await aiStreamHandler.fetch(new Request(
      'https://yudai.app/api/ai/sessions/session_123/stream',
      {
        body: JSON.stringify({
          context_card_ids: ['1'],
          messageId: 'user_1',
          messages: [{
            id: 'user_1',
            parts: [{ text: 'hello', type: 'text' }],
            role: 'user',
          }],
          repository: { branch: 'main', name: 'yudaiv3', owner: 'octocat' },
          session_id: 'session_123',
          trigger: 'submit-message',
        }),
        headers: {
          authorization: 'Bearer session-token',
          'content-type': 'application/json',
        },
        method: 'POST',
      }
    ));

    const streamText = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get('x-vercel-ai-ui-message-stream')).toBe('v1');
    expect(streamText).toContain('AI middleware is connected');
    expect(persistedTurn).not.toBeNull();
    const turn = persistedTurn as unknown as Record<string, unknown>;
    expect(turn).toMatchObject({
      context_card_ids: ['1'],
      model_used: 'middleware-fallback',
      trigger: 'submit-message',
      user_message_id: 'user_1',
      user_text: 'hello',
    });
    expect(String(turn.assistant_text)).toContain('AI middleware is connected');
  });

  it('requires auth before opening the backend realtime WebSocket', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({
      github_id: 'gh_1',
      github_username: 'tester',
      id: 7,
    }));

    const abortController = new AbortController();
    const response = await realtimeEventsHandler.fetch(new Request(
      'https://yudai.app/api/realtime/sessions/session_123/events',
      {
        headers: { authorization: 'Bearer session-token' },
        signal: abortController.signal,
      }
    ));
    const reader = response.body?.getReader();
    const ws = FakeWebSocket.instances[0];

    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toContain('text/event-stream');
    expect(ws?.url).toBe(
      'wss://backend.test/controller/sessions/session_123/ws/unified?internal_secret=internal-secret&internal_user_id=7'
    );

    ws?.emitMessage(JSON.stringify({
      payload: { session_id: 'session_123', status: 'connected' },
      type: 'status',
    }));
    const chunk = await reader?.read();
    abortController.abort();
    reader?.releaseLock();

    expect(new TextDecoder().decode(chunk?.value)).toContain('"status":"connected"');
  });

  it('does not open realtime when the internal middleware secret is missing', async () => {
    delete process.env.YUDAI_INTERNAL_MIDDLEWARE_SECRET;
    delete process.env.INTERNAL_MIDDLEWARE_SECRET;

    const response = await realtimeEventsHandler.fetch(new Request(
      'https://yudai.app/api/realtime/sessions/session_123/events',
      { headers: { authorization: 'Bearer session-token' } }
    ));

    expect(response.status).toBe(500);
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(fetch).not.toHaveBeenCalled();
  });
});
