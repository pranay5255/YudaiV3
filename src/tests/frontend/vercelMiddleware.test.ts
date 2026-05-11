import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CreateGitHubIssueInputSchema,
  StageToolInputSchema,
} from '../../api/ai/_lib/schema';

const { streamTextMock } = vi.hoisted(() => ({
  streamTextMock: vi.fn(),
}));

vi.mock('ai', async (importOriginal) => {
  const actual = await importOriginal<typeof import('ai')>();
  return {
    ...actual,
    streamText: streamTextMock,
  };
});

import aiStreamHandler from '../../api/ai/sessions/[sessionId]/stream';
import realtimeEventsHandler from '../../api/realtime/sessions/[sessionId]/events';

const originalEnv = { ...process.env };

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

async function* asyncParts<T>(items: T[]): AsyncGenerator<T> {
  for (const item of items) {
    yield item;
  }
}

describe('Vercel middleware handlers', () => {
  beforeEach(() => {
    process.env = { ...originalEnv };
    setMiddlewareEnv();
    FakeWebSocket.instances = [];
    streamTextMock.mockReset();
    vi.stubGlobal('fetch', vi.fn());
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('routes REST API paths directly to the production backend', () => {
    const vercelConfig = JSON.parse(
      readFileSync('vercel.json', 'utf8')
    ) as {
      rewrites: Array<{ destination: string; source: string }>;
    };

    expect(vercelConfig.rewrites).toEqual(expect.arrayContaining([
      {
        destination: 'https://api.yudai.app/daifu/:path*',
        source: '/daifu/:path*',
      },
      {
        destination: 'https://api.yudai.app/github/:path*',
        source: '/github/:path*',
      },
      {
        destination: 'https://api.yudai.app/controller/:path*',
        source: '/controller/:path*',
      },
    ]));
    expect(vercelConfig.rewrites).not.toEqual(expect.arrayContaining([
      expect.objectContaining({
        destination: expect.stringContaining('/api/proxy'),
      }),
    ]));
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

  it('streams structured AI SDK output, tool activity, and persists data parts', async () => {
    process.env.OPENROUTER_API_KEY = 'openrouter-key';
    process.env.OPENROUTER_MODEL = 'openrouter/test-model';
    let persistedTurn: Record<string, unknown> | null = null;

    streamTextMock.mockImplementation(({ tools }) => {
      const toolOutput = tools.createGitHubIssue.execute({ issue_id: 'issue_1' }, {
        messages: [],
        toolCallId: 'tool_call_1',
      });

      return {
        fullStream: (async function* toolStream() {
          yield { id: 'tool_call_1', toolName: 'createGitHubIssue', type: 'tool-input-start' };
          yield {
            input: { issue_id: 'issue_1' },
            toolCallId: 'tool_call_1',
            toolName: 'createGitHubIssue',
            type: 'tool-call',
          };
          yield {
            input: { issue_id: 'issue_1' },
            output: await toolOutput,
            toolCallId: 'tool_call_1',
            toolName: 'createGitHubIssue',
            type: 'tool-result',
          };
        })(),
        output: Promise.resolve({
          actions: [{
            action_type: 'create_issue',
            label: 'Draft follow-up',
            labels: ['task'],
          }],
          probes: [],
          questions: [{
            multi_select: false,
            options: [{ id: 'tests', label: 'Tests first' }],
            question_id: 'q_ai_sdk',
            question_text: 'Which path should I validate?',
          }],
          text: 'Preparing issue publication.',
        }),
        partialOutputStream: asyncParts([
          { text: 'Preparing' },
          { text: 'Preparing issue publication.' },
        ]),
      };
    });

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
      if (url === 'https://backend.test/daifu/sessions/session_123/tools/create-github-issue') {
        return jsonResponse({
          execution_started: false,
          github_issue_number: 42,
          github_url: 'https://github.com/octocat/yudaiv3/issues/42',
          message: 'Created GitHub issue',
          requires_confirmation: true,
          success: true,
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
            parts: [{ text: 'publish issue_1', type: 'text' }],
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
    expect(streamText).toContain('Preparing');
    expect(streamText).toContain('issue publication.');
    expect(streamText).toContain('createGitHubIssue');
    expect(streamText).toContain('data-agent-question');
    expect(streamTextMock).toHaveBeenCalledWith(expect.objectContaining({
      stopWhen: expect.any(Function),
      tools: expect.objectContaining({
        createGitHubIssue: expect.any(Object),
        runArchitectMode: expect.any(Object),
        runCoderMode: expect.any(Object),
        runTesterMode: expect.any(Object),
      }),
    }));
    expect(fetch).not.toHaveBeenCalledWith(
      'https://openrouter.ai/api/v1/chat/completions',
      expect.anything()
    );
    expect(vi.mocked(fetch).mock.calls.map(([input]) => String(input)).some((url) => (
      url.includes('/chat') || url.includes('/llm')
    ))).toBe(false);

    const turn = persistedTurn as unknown as Record<string, unknown>;
    expect(turn).toMatchObject({
      assistant_text: 'Preparing issue publication.',
      model_used: 'test-model',
      user_text: 'publish issue_1',
    });
    expect(turn.actions).toEqual([
      expect.objectContaining({ action_type: 'create_issue', label: 'Draft follow-up' }),
    ]);
    expect(turn.data_parts).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: 'data-tool-result' }),
      expect.objectContaining({ type: 'data-agent-question' }),
    ]));
  });

  it('validates native tool inputs before backend execution', () => {
    expect(CreateGitHubIssueInputSchema.safeParse({}).success).toBe(false);
    expect(CreateGitHubIssueInputSchema.safeParse({ issue_id: 'issue_123' }).success)
      .toBe(true);

    expect(StageToolInputSchema.safeParse({}).success).toBe(false);
    expect(StageToolInputSchema.safeParse({ objective: 'Run Architect on issue #42' }).success)
      .toBe(true);
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
