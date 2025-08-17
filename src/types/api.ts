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
}

export interface ChatRequest {
  session_id?: string;
  message: ChatMessage;
  context_cards?: string[];
  repo_owner?: string;
  repo_name?: string;
}

export interface CreateChatMessageRequest {
  content: string;
  sender_type: 'user' | 'assistant' | 'system';
  role: 'user' | 'assistant' | 'system';
  context_cards?: string[];
  referenced_files?: string[];
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
// SESSION API TYPES
// ============================================================================

export interface CreateSessionDaifuRequest {
  repo_owner: string;
  repo_name: string;
  repo_branch?: string;
  title?: string;
  description?: string;
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
}

export interface SessionContextResponse {
  session: SessionResponse;
  messages: ChatMessageResponse[];
  context_cards: string[];
  repository_info?: {
    owner: string;
    name: string;
    branch: string;
    full_name: string;
    html_url: string;
  };
  file_embeddings_count: number;
  statistics?: {
    total_messages: number;
    total_tokens: number;
    total_cost: number;
    session_duration: number;
    user_issues_count?: number;
    file_embeddings_count?: number;
  };
  user_issues?: UserIssueResponse[];
  file_embeddings?: FileEmbeddingResponse[];
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
  context_cards?: string[];
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
// USER ISSUES & FILE EMBEDDINGS API TYPES
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
}

export interface FileEmbeddingResponse {
  id: number;
  session_id: number;
  repository_id?: number;
  file_path: string;
  file_name: string;
  file_type: string;
  chunk_index: number;
  tokens: number;
  file_metadata?: Record<string, unknown>;
  created_at: string;
}

// ============================================================================
// CONTEXT CARDS & FILE EMBEDDINGS API TYPES
// ============================================================================

export interface CreateContextCardRequest {
  title: string;
  description: string;
  source: 'chat' | 'file-deps' | 'upload';
  tokens: number;
  content?: string;
}

export interface ContextCardResponse {
  id: number;
  session_id: number;
  title: string;
  description: string;
  source: string;
  tokens: number;
  content?: string;
  created_at: string;
  updated_at?: string;
}

export interface CreateFileEmbeddingRequest {
  file_path: string;
  file_name: string;
  file_type: string;
  chunk_index: number;
  tokens: number;
  file_metadata?: Record<string, unknown>;
}

export interface FileEmbeddingResponse {
  id: number;
  session_id: number;
  repository_id?: number;
  file_path: string;
  file_name: string;
  file_type: string;
  chunk_index: number;
  tokens: number;
  file_metadata?: Record<string, unknown>;
  created_at: string;
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