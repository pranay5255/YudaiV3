import { z } from 'zod';

export const ProjectConfigSchema = z.object({
  projectName: z.string(),
  repoPath: z.string(),
  cliConfig: z.record(z.any()).optional(),
});

export type ProjectConfig = z.infer<typeof ProjectConfigSchema>;
