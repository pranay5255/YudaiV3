import { z } from 'zod';

export const DaifuActionSchema = z.object({
  action_type: z.string().min(1).max(50),
  label: z.string().min(1).max(100),
  issue_title: z.string().max(200).nullable().optional(),
  issue_description: z.string().max(2000).nullable().optional(),
  labels: z.array(z.string().min(1).max(80)).nullable().optional(),
});

export const DaifuQuestionOptionSchema = z.object({
  id: z.string().min(1).max(128),
  label: z.string().min(1).max(255),
});

export const DaifuQuestionSchema = z.object({
  question_id: z.string().min(1).max(128).optional(),
  question_text: z.string().min(1).max(10000),
  options: z.array(DaifuQuestionOptionSchema).default([]),
  multi_select: z.boolean().default(false),
});

export const DaifuProbeSchema = z.object({
  query: z.string().min(1).max(1000),
  reason: z.string().max(1000).optional(),
});

export const DaifuResponseSchema = z.object({
  text: z.string().describe('User-facing assistant response in concise Markdown.'),
  questions: z.array(DaifuQuestionSchema).describe('Clarifying questions to ask the user.'),
  probes: z.array(DaifuProbeSchema).describe('Read-only repository exploration probes to request.'),
  actions: z.array(DaifuActionSchema).describe('Frontend actions, such as creating a drafted issue.'),
});

export const CreateGitHubIssueInputSchema = z.object({
  issue_id: z.string().min(1).max(255).describe('The existing Yudai drafted issue id to publish to GitHub.'),
});

export const StageToolInputSchema = z.object({
  objective: z.string().min(1).max(10000).describe('The concrete objective for this Daifu stage run.'),
});

export const CreateGitHubIssueToolOutputSchema = z.object({
  success: z.boolean(),
  github_url: z.string(),
  message: z.string(),
  github_issue_number: z.number().int().nullable().optional(),
  execution_started: z.boolean().optional(),
  execution_id: z.string().nullable().optional(),
  execution_status: z.string().nullable().optional(),
  execution_error: z.string().nullable().optional(),
  requires_confirmation: z.boolean().optional(),
  confirmation_question_id: z.string().nullable().optional(),
  pending_tool: z.string().nullable().optional(),
}).passthrough();

export const StageToolOutputSchema = z.object({
  execution_id: z.string(),
  session_id: z.string(),
  mode: z.string(),
  status: z.string(),
  plan: z.array(z.string()).default([]),
  started_at: z.string(),
  completed_at: z.string().nullable().optional(),
  cancel_requested: z.boolean().default(false),
  waiting_for_input: z.boolean().default(false),
  current_mode_execution_id: z.string().nullable().optional(),
  detail: z.string().nullable().optional(),
}).passthrough();

export type DaifuAction = z.infer<typeof DaifuActionSchema>;
export type DaifuProbe = z.infer<typeof DaifuProbeSchema>;
export type DaifuQuestion = z.infer<typeof DaifuQuestionSchema>;
export type DaifuResponse = z.infer<typeof DaifuResponseSchema>;
export type CreateGitHubIssueToolOutput = z.infer<typeof CreateGitHubIssueToolOutputSchema>;
export type StageToolOutput = z.infer<typeof StageToolOutputSchema>;
