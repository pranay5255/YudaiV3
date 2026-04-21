import type { components, paths } from './generated';

export type ApiPaths = paths;
export type ApiSchemas = components['schemas'];
export type ApiSchema<Name extends keyof ApiSchemas> = ApiSchemas[Name];

export type Session = ApiSchema<'SessionResponse'>;
export type SessionContext = ApiSchema<'SessionContextResponse'>;
export type ChatMessage = ApiSchema<'ChatMessageResponse'>;
export type ChatRequest = ApiSchema<'ChatRequest'>;
export type ChatResponse = ApiSchema<'ChatResponse'>;
export type CreateSessionRequest = ApiSchema<'CreateSessionRequest'>;
export type UpdateSessionRequest = ApiSchema<'UpdateSessionRequest'>;
export type ExecutionRequest = ApiSchema<'ExecutionRequest'>;
export type ExecutionResponse = ApiSchema<'ExecutionResponse'>;
export type ExecutionStatus = ApiSchema<'ExecutionStatusResponse'>;
export type Runtime = ApiSchema<'RuntimeResponse'>;
export type Sandbox = ApiSchema<'SandboxResponse'>;
export type GitHubRepository = ApiSchema<'GitHubRepositoryResponse'>;
export type GitHubBranch = ApiSchema<'GitHubBranchResponse'>;
export type User = ApiSchema<'ValidateSessionResponse'>;
