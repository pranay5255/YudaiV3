import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
  type UIMessageChunk,
  type UIMessageStreamWriter,
} from 'ai';
import {
  buildBackendHttpHeaders,
  getBackendBaseUrl,
  isAuthResult,
  jsonResponse,
  requireAuthenticatedUser,
  type AuthenticatedRequest,
} from '../../../_lib/backend';

type AiStreamRequestBody = {
  context_card_ids?: string[];
  messageId?: string | null;
  messages?: unknown[];
  repository?: {
    branch?: string;
    name?: string;
    owner?: string;
  } | null;
  session_id?: string;
  trigger?: string;
};

type BackendAiContext = {
  context_cards?: Array<{
    id: number;
    title: string;
    content: string;
  }>;
  messages?: Array<{
    message_text: string;
    role: string;
  }>;
  pending_questions?: unknown[];
  repository_info?: Record<string, unknown> | null;
  session?: Record<string, unknown>;
};

type ModelMessage = {
  role: 'assistant' | 'system' | 'user';
  content: string;
};

const getSessionIdFromPath = (request: Request): string | null => {
  const match = new URL(request.url).pathname.match(/\/sessions\/([^/]+)\/stream$/);
  return match ? decodeURIComponent(match[1]) : null;
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const textFromMessage = (message: unknown): string => {
  if (!isRecord(message)) {
    return '';
  }

  const parts = Array.isArray(message.parts) ? message.parts : [];
  const partText = parts
    .map((part) => {
      if (!isRecord(part) || part.type !== 'text') {
        return '';
      }
      return typeof part.text === 'string' ? part.text : '';
    })
    .filter(Boolean)
    .join('\n');

  if (partText) {
    return partText;
  }

  return typeof message.content === 'string' ? message.content : '';
};

const latestUserText = (messages: unknown[] | undefined): string => {
  for (const message of [...(messages || [])].reverse()) {
    if (isRecord(message) && message.role === 'user') {
      const text = textFromMessage(message).trim();
      if (text) {
        return text;
      }
    }
  }
  return '';
};

const getModelName = (): string => (
  process.env.OPENROUTER_MODEL ||
  process.env.MSWEA_MODEL_NAME?.replace(/^openrouter\//, '') ||
  'x-ai/grok-4-fast'
);

const buildModelMessages = (
  body: AiStreamRequestBody,
  context: BackendAiContext,
  userText: string
): ModelMessage[] => {
  const repository = body.repository || context.repository_info || {};
  const cards = (context.context_cards || [])
    .slice(0, 8)
    .map((card) => `### ${card.title}\n${card.content}`)
    .join('\n\n');

  const system = [
    'You are Yudai, an engineering agent working inside a repository session.',
    'Answer concisely, use the supplied repository/session context, and emit plain assistant text.',
    `Repository: ${JSON.stringify(repository)}`,
    cards ? `Context cards:\n${cards}` : '',
  ].filter(Boolean).join('\n\n');

  const history = (context.messages || [])
    .slice(-12)
    .map((message): ModelMessage | null => {
      const role = message.role === 'assistant' ? 'assistant' : 'user';
      const content = String(message.message_text || '').trim();
      return content ? { role, content } : null;
    })
    .filter((message): message is ModelMessage => Boolean(message));

  return [
    { role: 'system', content: system },
    ...history,
    { role: 'user', content: userText },
  ];
};

const fetchBackendJson = async <T>(
  auth: AuthenticatedRequest,
  request: Request,
  path: string,
  body: unknown
): Promise<T> => {
  const response = await fetch(`${getBackendBaseUrl()}${path}`, {
    method: 'POST',
    headers: buildBackendHttpHeaders(auth, request, true),
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Backend ${path} failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
};

async function* streamOpenRouterText(messages: ModelMessage[]): AsyncGenerator<string> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    yield 'AI middleware is connected. Configure OPENROUTER_API_KEY to enable model responses.';
    return;
  }

  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${apiKey}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      messages,
      model: getModelName(),
      stream: true,
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Model stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      return;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) {
        continue;
      }

      const raw = trimmed.slice(5).trim();
      if (!raw || raw === '[DONE]') {
        continue;
      }

      const payload = JSON.parse(raw) as {
        choices?: Array<{ delta?: { content?: string } }>;
      };
      const delta = payload.choices?.[0]?.delta?.content;
      if (delta) {
        yield delta;
      }
    }
  }
}

const writeStatus = (
  writer: UIMessageStreamWriter<UIMessage>,
  message: string,
  tone: 'error' | 'info' | 'success' = 'info'
): void => {
  writer.write({
    type: 'data-status',
    data: { message, tone },
    transient: true,
  } as UIMessageChunk);
};

export default {
  async fetch(request: Request): Promise<Response> {
    if (request.method !== 'POST') {
      return jsonResponse(405, { detail: 'Method not allowed' });
    }

    const auth = await requireAuthenticatedUser(request);
    if (!isAuthResult(auth)) {
      return auth;
    }

    const sessionId = getSessionIdFromPath(request);
    if (!sessionId) {
      return jsonResponse(400, { detail: 'Missing session id' });
    }

    const body = await request.json() as AiStreamRequestBody;
    if (body.session_id !== sessionId) {
      return jsonResponse(400, { detail: 'Session ID mismatch between URL and request body' });
    }

    const userText = latestUserText(body.messages);
    if (!userText) {
      return jsonResponse(400, { detail: 'Missing user message text' });
    }

    const assistantTextId = `assistant_${crypto.randomUUID()}`;
    let assistantText = '';

    const stream = createUIMessageStream({
      originalMessages: (body.messages || []) as UIMessage[],
      async execute({ writer }) {
        try {
          writeStatus(writer, 'Loading session context');
          const context = await fetchBackendJson<BackendAiContext>(
            auth,
            request,
            `/daifu/sessions/${encodeURIComponent(sessionId)}/ai-context`,
            {
              context_card_ids: body.context_card_ids || [],
              messages: body.messages || [],
              repository: body.repository || null,
            }
          );

          if ((context.pending_questions || []).length > 0) {
            writeStatus(writer, 'Waiting on pending clarification');
          } else {
            writeStatus(writer, 'Generating response');
          }

          writer.write({ type: 'text-start', id: assistantTextId });

          for await (const delta of streamOpenRouterText(
            buildModelMessages(body, context, userText)
          )) {
            assistantText += delta;
            writer.write({ type: 'text-delta', id: assistantTextId, delta });
          }

          writer.write({ type: 'text-end', id: assistantTextId });

          await fetchBackendJson(
            auth,
            request,
            `/daifu/sessions/${encodeURIComponent(sessionId)}/ai-turns`,
            {
              assistant_message_id: assistantTextId,
              assistant_text: assistantText,
              context_card_ids: body.context_card_ids || [],
              model_used: process.env.OPENROUTER_API_KEY ? getModelName() : 'middleware-fallback',
              trigger: body.trigger || null,
              ui_messages: body.messages || [],
              user_message_id: body.messageId || null,
              user_text: userText,
            }
          );

          writeStatus(writer, 'Response saved', 'success');
        } catch (error) {
          const message = error instanceof Error ? error.message : 'AI stream failed';
          writeStatus(writer, message, 'error');
          writer.write({ type: 'error', errorText: message });
        }
      },
    });

    return createUIMessageStreamResponse({ stream });
  },
};
