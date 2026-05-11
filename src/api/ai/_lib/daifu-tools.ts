import { tool } from 'ai';
import {
  CreateGitHubIssueInputSchema,
  CreateGitHubIssueToolOutputSchema,
  StageToolInputSchema,
  StageToolOutputSchema,
  type CreateGitHubIssueToolOutput,
  type StageToolOutput,
} from './schema.js';

type FetchBackendJson = <T>(path: string, body: unknown) => Promise<T>;
type StageToolName = 'run_architect_mode' | 'run_tester_mode' | 'run_coder_mode';

const parseStageToolInput = (input: unknown): { objective: string } => {
  const parsed = StageToolInputSchema.parse(input);
  if (typeof parsed.objective !== 'string' || !parsed.objective.trim()) {
    throw new Error('Stage tool objective is required');
  }
  return { objective: parsed.objective };
};

const executeStageTool = (
  fetchBackendJson: FetchBackendJson,
  sessionId: string,
  toolName: StageToolName,
  input: { objective: string }
): Promise<StageToolOutput> => (
  fetchBackendJson<StageToolOutput>(
    `/daifu/sessions/${encodeURIComponent(sessionId)}/execution/stage-tool`,
    {
      objective: input.objective,
      tool_name: toolName,
    }
  )
);

export const createDaifuTools = (
  fetchBackendJson: FetchBackendJson,
  sessionId: string
) => ({
  createGitHubIssue: tool({
    description: 'Publish an existing Yudai drafted issue to GitHub. Requires an existing issue_id from session issues.',
    inputSchema: CreateGitHubIssueInputSchema,
    outputSchema: CreateGitHubIssueToolOutputSchema,
    execute: (input): Promise<CreateGitHubIssueToolOutput> => {
      const parsed = CreateGitHubIssueInputSchema.parse(input);
      return fetchBackendJson<CreateGitHubIssueToolOutput>(
        `/daifu/sessions/${encodeURIComponent(sessionId)}/tools/create-github-issue`,
        { issue_id: parsed.issue_id }
      );
    },
  }),
  runArchitectMode: tool({
    description: 'Start Daifu Architect mode for a concrete objective.',
    inputSchema: StageToolInputSchema,
    outputSchema: StageToolOutputSchema,
    execute: (input): Promise<StageToolOutput> => {
      const parsed = parseStageToolInput(input);
      return executeStageTool(fetchBackendJson, sessionId, 'run_architect_mode', parsed);
    },
  }),
  runTesterMode: tool({
    description: 'Start Daifu Tester mode for a concrete objective.',
    inputSchema: StageToolInputSchema,
    outputSchema: StageToolOutputSchema,
    execute: (input): Promise<StageToolOutput> => {
      const parsed = parseStageToolInput(input);
      return executeStageTool(fetchBackendJson, sessionId, 'run_tester_mode', parsed);
    },
  }),
  runCoderMode: tool({
    description: 'Start Daifu Coder mode for a concrete objective.',
    inputSchema: StageToolInputSchema,
    outputSchema: StageToolOutputSchema,
    execute: (input): Promise<StageToolOutput> => {
      const parsed = parseStageToolInput(input);
      return executeStageTool(fetchBackendJson, sessionId, 'run_coder_mode', parsed);
    },
  }),
});

export type DaifuTools = ReturnType<typeof createDaifuTools>;
