export interface CSVMetadata {
  filename: string;
  schema: Record<string, string>;
  rowCount: number;
  columnCount: number;
}

export interface ProjectConfig {
  projectName: string;
  repoPath: string;
  cliConfig: Record<string, any> | null;
}

export interface PromptContext {
  prompt: string;
  tokens: number;
  generatedCode: string | null;
}

export interface RunCLIRequest {
  args: string[];
}

export interface RunCLIResponse {
  stdout: string;
  stderr: string;
}
