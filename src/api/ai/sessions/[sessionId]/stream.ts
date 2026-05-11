import {
  Output,
  createUIMessageStream,
  createUIMessageStreamResponse,
  stepCountIs,
  streamText,
  type TextStreamPart,
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
} from '../../../_lib/backend.js';
import { createDaifuTools, type DaifuTools } from '../../_lib/daifu-tools.js';
import {
  buildModelMessages,
  latestUserText,
  type AiStreamRequestBody,
  type BackendAiContext,
} from '../../_lib/prompt-builder.js';
import { getDaifuModel, getModelName, getModelTemperature } from '../../_lib/provider.js';
import {
  DaifuResponseSchema,
  type DaifuAction,
  type DaifuProbe,
  type DaifuQuestion,
  type DaifuResponse,
} from '../../_lib/schema.js';

type PersistedDataPart = {
  data: unknown;
  id?: string;
  type: string;
};

const getSessionIdFromPath = (request: Request): string | null => {
  const match = new URL(request.url).pathname.match(/\/sessions\/([^/]+)\/stream$/);
  return match ? decodeURIComponent(match[1]) : null;
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
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Backend ${path} failed with status ${response.status}${detail ? `: ${detail}` : ''}`
    );
  }

  return response.json() as Promise<T>;
};

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

const writeTextDelta = (
  writer: UIMessageStreamWriter<UIMessage>,
  id: string,
  delta: string
): void => {
  if (!delta) {
    return;
  }

  writer.write({ type: 'text-delta', id, delta } as UIMessageChunk);
};

const stringifyError = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }

  try {
    return JSON.stringify(error);
  } catch {
    return 'Tool execution failed';
  }
};

const writeToolStreamPart = (
  writer: UIMessageStreamWriter<UIMessage>,
  part: TextStreamPart<DaifuTools>,
  dataParts: PersistedDataPart[]
): void => {
  switch (part.type) {
    case 'tool-input-start':
      writer.write({
        type: 'tool-input-start',
        toolCallId: part.id,
        toolName: part.toolName,
      } as UIMessageChunk);
      return;
    case 'tool-input-delta':
      writer.write({
        type: 'tool-input-delta',
        toolCallId: part.id,
        inputTextDelta: part.delta,
      } as UIMessageChunk);
      return;
    case 'tool-call':
      writer.write(part.invalid ? {
        type: 'tool-input-error',
        toolCallId: part.toolCallId,
        toolName: part.toolName,
        input: part.input,
        errorText: stringifyError(part.error),
      } as UIMessageChunk : {
        type: 'tool-input-available',
        toolCallId: part.toolCallId,
        toolName: part.toolName,
        input: part.input,
      } as UIMessageChunk);
      return;
    case 'tool-result':
      writer.write({
        type: 'tool-output-available',
        toolCallId: part.toolCallId,
        output: part.output,
      } as UIMessageChunk);
      dataParts.push({
        data: {
          output: part.output,
          tool_call_id: part.toolCallId,
          tool_name: part.toolName,
        },
        type: 'data-tool-result',
      });
      return;
    case 'tool-error':
      writer.write({
        type: 'tool-output-error',
        toolCallId: part.toolCallId,
        errorText: stringifyError(part.error),
      } as UIMessageChunk);
      dataParts.push({
        data: {
          error: stringifyError(part.error),
          tool_call_id: part.toolCallId,
          tool_name: part.toolName,
        },
        type: 'data-tool-error',
      });
      return;
    case 'tool-output-denied':
      writer.write({
        type: 'tool-output-denied',
        toolCallId: part.toolCallId,
      } as UIMessageChunk);
      return;
    case 'start-step':
      writer.write({ type: 'start-step' } as UIMessageChunk);
      return;
    default:
      return;
  }
};

const writeDataPart = (
  writer: UIMessageStreamWriter<UIMessage>,
  dataParts: PersistedDataPart[],
  part: PersistedDataPart
): void => {
  dataParts.push(part);
  writer.write(part as UIMessageChunk);
};

const writeStructuredOutputParts = (
  writer: UIMessageStreamWriter<UIMessage>,
  assistantTextId: string,
  output: DaifuResponse,
  dataParts: PersistedDataPart[]
): void => {
  output.actions.forEach((action: DaifuAction, index) => {
    writeDataPart(writer, dataParts, {
      data: action,
      id: `${assistantTextId}_action_${index}`,
      type: 'data-action',
    });
  });

  output.questions.forEach((question: DaifuQuestion, index) => {
    const questionId = question.question_id || `q_${crypto.randomUUID().replace(/-/g, '').slice(0, 10)}`;
    writeDataPart(writer, dataParts, {
      data: {
        ...question,
        question_id: questionId,
      },
      id: `${assistantTextId}_question_${index}`,
      type: 'data-agent-question',
    });
  });

  output.probes.forEach((probe: DaifuProbe, index) => {
    writeDataPart(writer, dataParts, {
      data: probe,
      id: `${assistantTextId}_probe_${index}`,
      type: 'data-agent-probe',
    });
  });
};

const getFallbackText = (): string | null => {
  if (!process.env.OPENROUTER_API_KEY) {
    return 'AI middleware is connected. Configure OPENROUTER_API_KEY to enable model responses.';
  }
  if (!getModelName()) {
    return 'AI middleware is connected. Configure OPENROUTER_MODEL or MSWEA_MODEL_NAME to enable model responses.';
  }
  return null;
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
    let textOpen = false;

    const stream = createUIMessageStream({
      originalMessages: (body.messages || []) as UIMessage[],
      async execute({ writer }) {
        const dataParts: PersistedDataPart[] = [];
        const backendJson = <T>(path: string, payload: unknown): Promise<T> => (
          fetchBackendJson<T>(auth, request, path, payload)
        );

        try {
          writeStatus(writer, 'Loading session context');
          const context = await backendJson<BackendAiContext>(
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

          writer.write({ type: 'text-start', id: assistantTextId } as UIMessageChunk);
          textOpen = true;

          const fallbackText = getFallbackText();
          const configuredModel = getDaifuModel();

          if (fallbackText || !configuredModel) {
            assistantText = fallbackText || 'AI middleware is connected. Configure model settings to enable responses.';
            writeTextDelta(writer, assistantTextId, assistantText);
          } else {
            const result = streamText({
              messages: buildModelMessages(body, context, userText),
              model: configuredModel.model,
              output: Output.object<DaifuResponse>({
                description: 'Daifu assistant response, structured UI data, and optional tool-driven follow-up.',
                name: 'daifu_response',
                schema: DaifuResponseSchema,
              }),
              stopWhen: stepCountIs(10),
              temperature: getModelTemperature(),
              tools: createDaifuTools(backendJson, sessionId),
            });

            let streamedText = '';
            let latestPartialText = '';

            await Promise.all([
              (async () => {
                for await (const partial of result.partialOutputStream) {
                  const nextText = typeof partial?.text === 'string' ? partial.text : '';
                  if (!nextText || nextText === latestPartialText) {
                    continue;
                  }
                  latestPartialText = nextText;

                  if (!nextText.startsWith(streamedText)) {
                    continue;
                  }

                  const delta = nextText.slice(streamedText.length);
                  streamedText = nextText;
                  assistantText = nextText;
                  writeTextDelta(writer, assistantTextId, delta);
                }
              })(),
              (async () => {
                for await (const part of result.fullStream) {
                  if (part.type === 'error') {
                    throw new Error(stringifyError(part.error));
                  }
                  writeToolStreamPart(writer, part, dataParts);
                }
              })(),
            ]);

            const output = DaifuResponseSchema.parse(await result.output);
            const finalText = output.text || streamedText;
            if (finalText.startsWith(streamedText)) {
              writeTextDelta(writer, assistantTextId, finalText.slice(streamedText.length));
            } else if (!streamedText) {
              writeTextDelta(writer, assistantTextId, finalText);
            }
            assistantText = finalText;
            writeStructuredOutputParts(writer, assistantTextId, output, dataParts);
          }

          writer.write({ type: 'text-end', id: assistantTextId } as UIMessageChunk);
          textOpen = false;

          await backendJson(
            `/daifu/sessions/${encodeURIComponent(sessionId)}/ai-turns`,
            {
              actions: dataParts
                .filter((part) => part.type === 'data-action')
                .map((part) => part.data),
              assistant_message_id: assistantTextId,
              assistant_text: assistantText,
              context_card_ids: body.context_card_ids || [],
              data_parts: dataParts,
              model_used: getModelName() || 'middleware-fallback',
              trigger: body.trigger || null,
              ui_messages: body.messages || [],
              user_message_id: body.messageId || null,
              user_text: userText,
            }
          );

          writeStatus(writer, 'Response saved', 'success');
        } catch (error) {
          const message = error instanceof Error ? error.message : 'AI stream failed';
          if (textOpen) {
            writer.write({ type: 'text-end', id: assistantTextId } as UIMessageChunk);
            textOpen = false;
          }
          writeStatus(writer, message, 'error');
          writer.write({ type: 'error', errorText: message });
        }
      },
    });

    return createUIMessageStreamResponse({ stream });
  },
};
