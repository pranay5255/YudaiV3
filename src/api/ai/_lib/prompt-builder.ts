import type { ModelMessage } from 'ai';

export type AiStreamRequestBody = {
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

export type BackendAiContext = {
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

export const isRecord = (value: unknown): value is Record<string, unknown> => (
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

export const latestUserText = (messages: unknown[] | undefined): string => {
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

export const buildModelMessages = (
  body: AiStreamRequestBody,
  context: BackendAiContext,
  userText: string
): ModelMessage[] => {
  const repository = body.repository || context.repository_info || {};
  const cards = (context.context_cards || [])
    .slice(0, 8)
    .map((card) => `### ${card.title}\n${card.content}`)
    .join('\n\n');
  const pendingQuestions = context.pending_questions?.length
    ? JSON.stringify(context.pending_questions)
    : '';

  const system = [
    'You are Yudai, an engineering agent working inside a repository session.',
    'Answer concisely, use the supplied repository/session context, and put user-facing Markdown in the `text` field.',
    'Return only the structured object requested by the response schema.',
    'Use `questions` for clarification questions. Use `actions` for frontend buttons. Use `probes` for read-only repository exploration requests.',
    'Use native tools when the user explicitly asks to publish an existing drafted issue or start Architect, Tester, or Coder mode.',
    'Do not emit legacy Button{}, Question{}, Probe{}, Tool{}, XML, or fenced JSON directives in `text`.',
    `Repository: ${JSON.stringify(repository)}`,
    cards ? `Context cards:\n${cards}` : '',
    pendingQuestions ? `Pending user questions:\n${pendingQuestions}` : '',
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
