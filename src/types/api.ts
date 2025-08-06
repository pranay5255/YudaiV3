/**
 * Unified API Types
 * All request/response interfaces for API communication
 */

// ============================================================================
// AUTH API TYPES
// ============================================================================

export interface CreateSessionRequest {
  github_token: string;
}

export interface CreateSessionResponse {
  session_token: string;
  expires_at: string;
  user: {
    id: number;
    github_username: string;
    github_user_id: string;
    email: string;
    display_name: string;
    avatar_url: string;
    created_at: string;
    last_login: string;
  };
}

export interface ValidateSessionResponse {
  id: number;
  github_username: string;
  github_id: string;
  display_name: string;
  email: string;
  avatar_url: string;
}

export interface LogoutRequest {
  session_token: string;
}

export interface LogoutResponse {
  success: boolean;
  message: string;
}

export interface LoginUrlResponse {
  login_url: string;
}

// ============================================================================
// CHAT API TYPES
// ============================================================================

export interface ChatMessage {
  content: string;
  is_code: boolean;
}

export interface ChatRequest {
  session_id?: string;
  message: ChatMessage;
  context_cards?: string[];
  repo_owner?: string;
  repo_name?: string;
}

export interface ChatResponse {
  reply: string;
  conversation: [string, string][];
  message_id: string;
  processing_time: number;
  session_id?: string;
}

export interface ChatContextMessage {
  id: string;
  content: string;
  isCode: boolean;
  timestamp: string;
}

export interface CreateIssueFromChatResponse {
  success: boolean;
  issue: {
    id: number;
    issue_id: string;
    user_id: number;
    title: string;
    description?: string;
    issue_text_raw: string;
    issue_steps?: string[];
    session_id?: string;
    context_card_id?: number;
    context_cards?: string[];
    ideas?: string[];
    repo_owner?: string;
    repo_name?: string;
    priority: string;
    status: string;
    agent_response?: string;
    processing_time?: number;
    tokens_used: number;
    github_issue_url?: string;
    github_issue_number?: number;
    created_at: string;
    updated_at?: string;
    processed_at?: string;
  };
  message: string;
}

// ============================================================================
// ISSUE MANAGEMENT API TYPES
// ============================================================================

export interface FileContextItem {
  id: string;
  name: string;
  type: string;
  tokens: number;
  category: string;
  path?: string;
}

export interface CreateIssueWithContextRequest {
  title: string;
  description?: string;
  chat_messages: ChatContextMessage[];
  file_context: FileContextItem[];
  repository_info?: {
    owner: string;
    name: string;
    branch?: string;
  };
  priority?: string;
}

export interface GitHubIssuePreview {
  title: string;
  body: string;
  labels: string[];
  assignees: string[];
  repository_info?: {
    owner: string;
    name: string;
    branch?: string;
  };
  metadata: {
    chat_messages_count: number;
    file_context_count: number;
    total_tokens: number;
    generated_at: string;
    generation_method: string;
  };
}

export interface IssueCreationResponse {
  success: boolean;
  preview_only: boolean;
  github_preview: GitHubIssuePreview;
  user_issue?: {
    id: number;
    issue_id: string;
    title: string;
    description?: string;
    issue_text_raw: string;
  };
  message: string;
}

export interface CreateGitHubIssueResponse {
  success: boolean;
  github_url: string;
  message: string;
}

// ============================================================================
// REPOSITORY API TYPES
// ============================================================================

export interface GitHubRepositoryAPI {
  id: number;
  name: string;
  full_name: string;
  description: string;
  private: boolean;
  html_url: string;
  default_branch: string;
}

export interface GitHubBranchAPI {
  name: string;
  commit: {
    sha: string;
    url: string;
  };
}

export interface RepositoryResponse {
  repositories: GitHubRepositoryAPI[];
}

export interface RepositoryDetailsResponse {
  id: string;
  name: string;
  owner: string;
  description?: string;
  private: boolean;
  default_branch: string;
  branches: string[];
}

// ============================================================================
// FILE DEPENDENCIES API TYPES
// ============================================================================

export interface FileAnalysisResponse {
  dependencies: FileContextItem[];
  total_tokens: number;
}

export interface FileDependencyNode {
  id: string;
  name: string;
  type: string;
  tokens: number;
  Category: string;
  isDirectory?: boolean;
  children?: FileDependencyNode[];
}

export interface ExtractFileDependenciesRequest {
  repo_url: string;
}

export interface ExtractFileDependenciesResponse {
  children: FileDependencyNode[];
}

// ============================================================================
// COMMON TYPES
// ============================================================================

export interface ApiError {
  detail?: string;
  message?: string;
  status?: number;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  success: boolean;
}