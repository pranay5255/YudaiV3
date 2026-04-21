// DEPRECATED: This file is being phased out in favor of unified sessionTypes.ts
// All API types have been moved to src/types/sessionTypes.ts
//
// Migration Guide:
// - All types from this file are now available in src/types/sessionTypes.ts
// - Update your imports to use: import { TypeName } from '../types/sessionTypes'
//
// This file will be removed once all components migrate to the unified types

/**
 * DEPRECATED: Unified API Types
 * All request/response interfaces for API communication
 * @deprecated Use types from src/types/sessionTypes.ts instead
 */

// ============================================================================
// AUTH API TYPES
// ============================================================================

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

export interface ChatRequest {
  session_id?: string;
  message: {
    message_text: string;
  };
  repository?: {
    owner: string;
    name: string;
    branch?: string;
  };
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
  github_issue_number?: number;
  execution_started?: boolean;
  execution_id?: string;
  execution_status?: string;
  execution_error?: string;
  requires_confirmation?: boolean;
  confirmation_question_id?: string;
  pending_tool?: string;
}

export interface CreateGitHubIssueToolRequest {
  issue_id: string;
}

// ============================================================================
// SESSION API TYPES
// ============================================================================

export interface CreateSessionDaifuRequest {
  repo_owner: string;
  repo_name: string;
  repo_branch?: string;
  title?: string;
  description?: string;
}

export interface UpdateSessionRequest {
  title?: string;
  description?: string;
  repo_branch?: string;
}

export interface UpdateMessageRequest {
  message_text?: string;
  tokens?: number;
}

export interface SessionResponse {
  id: number;
  session_id: string;
  title?: string;
  description?: string;
  repo_owner?: string;
  repo_name?: string;
  repo_branch?: string;
  repo_context?: Record<string, unknown>;
  is_active: boolean;
  total_messages: number;
  total_tokens: number;
  created_at: string;
  updated_at?: string;
  last_activity?: string;
  runtime_id?: string;
  sandbox_id?: string;
  tunnel_url?: string;
}

export interface SessionContextResponse {
  session: SessionResponse;
  messages: ChatMessageResponse[];
  repository_info?: {
    owner: string;
    name: string;
    branch: string;
    full_name: string;
    html_url: string;
  };
  statistics?: {
    total_messages: number;
    total_tokens: number;
    total_cost: number;
    session_duration: number;
    user_issues_count?: number;
  };
  user_issues?: UserIssueResponse[];
}

export interface ChatMessageResponse {
  id: number;
  message_id: string;
  message_text: string;
  sender_type: string;
  role: string;
  is_code: boolean;
  tokens: number;
  model_used?: string;
  processing_time?: number;
  referenced_files?: string[];
  error_message?: string;
  created_at: string;
  updated_at?: string;
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
// USER ISSUES API TYPES
// ============================================================================

export interface UserIssueResponse {
  id: number;
  issue_id: string;
  user_id: number;
  title: string;
  description?: string;
  issue_text_raw: string;
  issue_steps?: string[];
  session_id?: string;
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
