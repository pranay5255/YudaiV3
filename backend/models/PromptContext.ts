import { z } from 'zod';

export const PromptContextSchema = z.object({
  prompt: z.string(),
  tokens: z.number().int().nonnegative(),
  generatedCode: z.string().optional(),
});

export type PromptContext = z.infer<typeof PromptContextSchema>;
