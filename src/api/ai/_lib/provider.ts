import { createOpenAICompatible } from '@ai-sdk/openai-compatible';
import type { LanguageModel } from 'ai';

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1';

export const normalizeOpenRouterModel = (value: string | undefined): string => (
  (value || '').trim().replace(/^openrouter\//, '')
);

export const getModelName = (): string | null => (
  normalizeOpenRouterModel(process.env.OPENROUTER_MODEL) ||
  normalizeOpenRouterModel(process.env.MSWEA_MODEL_NAME) ||
  null
);

export const getModelTemperature = (): number | undefined => {
  const raw = process.env.MODEL_TEMPERATURE?.trim();
  if (!raw) {
    return undefined;
  }
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error('MODEL_TEMPERATURE must be a number');
  }
  return value;
};

export const getDaifuModel = (): { model: LanguageModel; modelName: string } | null => {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return null;
  }

  const modelName = getModelName();
  if (!modelName) {
    return null;
  }

  const openrouter = createOpenAICompatible({
    apiKey,
    baseURL: OPENROUTER_BASE_URL,
    includeUsage: true,
    name: 'openrouter',
    supportsStructuredOutputs: true,
  });

  return {
    model: openrouter.chatModel(modelName),
    modelName,
  };
};
