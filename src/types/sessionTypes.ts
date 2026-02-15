/**
 * Unified Session Types
 * Consolidated type definitions for all session-related operations
 */

// ============================================================================
// CORE SESSION TYPES
// ============================================================================

export interface Session {
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

export interface SessionContext {
  session: Session | null;
  messages: ChatMessage[];
  context_cards: string[];
  repository_info?: RepositoryInfo;
  file_embeddings_count: number;
  statistics?: SessionStatistics;
  user_issues?: UserIssue[];
  file_embeddings?: FileItem[];
}

// ============================================================================
// CHAT MESSAGE TYPES
// ============================================================================

export interface ChatMessage {
  id: number;
  message_id: string;
  message_text: string;
  sender_type: 'user' | 'assistant' | 'system';
  role: 'user' | 'assistant' | 'system';
  tokens: number;
  model_used?: string;
  processing_time?: number;
  context_cards?: string[];
  referenced_files?: string[];
  error_message?: string;
  actions?: ChatAction[];
  created_at: string;
  updated_at?: string;
}

// ============================================================================
// CONTEXT CARD TYPES
// ============================================================================

export interface ContextCard {
  id: string;
  title: string;
  description: string;
  tokens: number;
  source: 'chat' | 'file-deps' | 'upload';
  content?: string;
}

// ============================================================================
// FILE DEPENDENCY TYPES
// ============================================================================

export interface FileItem {
  id: string;
  name: string;
  path?: string;
  type: 'INTERNAL' | 'EXTERNAL';
  tokens: number;
  category: string;
  isDirectory?: boolean;
  children?: FileItem[];
  expanded?: boolean;
  content_size?: number;
  created_at?: string;
  file_name?: string;
  file_path?: string;
  file_type?: string;
  content_summary?: string;
}

// ============================================================================
// USER ISSUE TYPES
// ============================================================================

export interface UserIssue {
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

// ============================================================================
// SUPPORTING TYPES
// ============================================================================

export interface RepositoryInfo {
  owner: string;
  name: string;
  branch: string;
  full_name: string;
  html_url: string;
}

export interface SessionStatistics {
  total_messages: number;
  total_tokens: number;
  total_cost: number;
  session_duration: number;
  user_issues_count?: number;
  file_embeddings_count?: number;
}

export interface AgentStatus {
  type: 'daifu' | 'architect' | 'coder' | 'tester';
  status: 'idle' | 'processing' | 'completed' | 'error';
  progress?: number;
  message?: string;
  started_at?: string;
  completed_at?: string;
}

// ============================================================================
// ISSUE CREATION & MANAGEMENT TYPES
// ============================================================================

export interface ChatAction {
  action_type: string;
  label: string;
  issue_title?: string;
  issue_description?: string;
  labels?: string[];
}

export interface CreateUserIssueRequest {
  title: string;
  issue_text_raw: string;
  description?: string;
  session_id?: string;
  context_card_id?: number;
  context_cards?: string[];
  ideas?: string[];
  repo_owner?: string;
  repo_name?: string;
  priority: string;
  issue_steps?: string[];
}

export interface IssueGenerationRequest {
  title: string;
  description: string;
  chat_messages: ChatContextMessage[];
  file_context: FileContextItem[];
  repository_info?: {
    owner: string;
    name: string;
    branch?: string;
  };
  priority?: string;
}

export interface IssueGenerationResponse {
  title: string;
  body: string;
  labels: string[];
  assignees: string[];
  processing_time: number;
  tokens_used: number;
  llm_response: string;
  raw_response: Record<string, unknown>;
}

// ============================================================================
// GITHUB CONTEXT TYPES
// ============================================================================

export interface GitHubRepositoryContext {
  repository: GitHubRepositoryInfo;
  branches: GitHubBranchInfo[];
  contributors: GitHubContributorInfo[];
  fetched_at: string;
  owner: string;
  name: string;
}

export interface GitHubRepositoryInfo {
  id?: number;
  name: string;
  full_name: string;
  description?: string;
  language?: string;
  stargazers_count?: number;
  forks_count?: number;
  open_issues_count?: number;
  default_branch?: string;
  topics?: string[];
  created_at?: string;
  updated_at?: string;
  pushed_at?: string;
  private?: boolean;
  html_url?: string;
}

export interface GitHubBranchInfo {
  name: string;
  protected?: boolean;
  commit_sha?: string;
}

export interface GitHubContributorInfo {
  login: string;
  contributions: number;
  avatar_url?: string;
}

export interface GitHubIssueInfo {
  number: number;
  title: string;
  state: string;
  created_at: string;
  labels: string[];
}

export interface GitHubCommitInfo {
  sha: string;
  message: string;
  author?: string;
  date?: string;
}

// ============================================================================
// CHAT PROCESSING TYPES
// ============================================================================

export interface ChatProcessingRequest {
  session_id: string;
  user_id: number;
  message_text: string;
  context_cards?: string[];
  repository?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

export interface ChatProcessingResponse {
  reply: string;
  message_id: string;
  processing_time: number;
  session_id: string;
  tokens_used?: number;
}

// ============================================================================
// REQUEST TYPES
// ============================================================================

export interface CreateSessionRequest {
  repo_owner: string;
  repo_name: string;
  repo_branch?: string;
  title?: string;
  description?: string;
  index_codebase?: boolean;
  index_max_file_size?: number;
}

export interface UpdateSessionRequest {
  title?: string;
  description?: string;
  repo_branch?: string;
}

export interface CreateContextCardRequest {
  title: string;
  description: string;
  source: 'chat' | 'file-deps' | 'upload';
  tokens: number;
  content?: string;
}

export interface UpdateContextCardRequest {
  title?: string;
  description?: string;
  content?: string;
}

export interface CreateFileEmbeddingRequest {
  file_path: string;
  file_name: string;
  file_type: string;
  chunk_index: number;
  tokens: number;
  file_metadata?: Record<string, unknown>;
}

export interface UpdateFileEmbeddingRequest {
  file_path?: string;
  file_name?: string;
  file_type?: string;
  file_content?: string;
  chunk_text?: string;
  chunk_index?: number;
  tokens?: number;
  file_metadata?: Record<string, unknown>;
}

export interface ChatRequest {
  session_id?: string;
  message: {
    message_text: string;
  };
  context_cards?: string[];
  repository?: {
    owner: string;
    name: string;
    branch?: string;
  };
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

export interface ChatContextMessage {
  id: string;
  content: string;
  isCode: boolean;
  timestamp: string;
}

export interface FileContextItem {
  id: string;
  name: string;
  type: string;
  tokens: number;
  category: string;
  path?: string;
}

// ============================================================================
// RESPONSE TYPES
// ============================================================================

export interface ChatResponse {
  reply: string;
  conversation: [string, string][];
  message_id: string;
  processing_time: number;
  session_id?: string;
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
    files_context_count: number;
    total_tokens: number;
    generated_at: string;
    generation_method: string;
    generated_by_llm?: boolean;
    processing_time?: number;
    tokens_used?: number;
    llm_model?: string;
    generated_from?: string;
    preview_generated_at?: string;
  };
}

// ============================================================================
// REPOSITORY TYPES
// ============================================================================

export interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  html_url: string;
  description?: string;
  clone_url?: string;
  language?: string;
  stargazers_count?: number;
  forks_count?: number;
  open_issues_count?: number;
  updated_at?: string;
  created_at?: string;
  pushed_at?: string;
  default_branch?: string;
  owner?: {
    login: string;
    id: number;
    avatar_url?: string;
    html_url?: string;
  };
}

export interface GitHubBranch {
  name: string;
  commit: {
    sha: string;
    url: string;
  };
  protected?: boolean;
}

export interface SelectedRepository {
  repository: GitHubRepository;
  branch: string;
}

// ============================================================================
// AUTH TYPES
// ============================================================================

export interface User {
  id: number;
  github_username: string;
  github_user_id: string;
  email?: string;
  display_name?: string;
  avatar_url?: string;
  created_at: string;
  last_login?: string;
}

// ============================================================================
// MUTATION TYPES FOR REACT QUERY
// ============================================================================

export interface CreateSessionMutationData {
  repoOwner: string;
  repoName: string;
  repoBranch?: string;
}

export interface AddContextCardMutationData {
  sessionId: string;
  card: {
    title: string;
    description: string;
    source: 'chat' | 'file-deps' | 'upload';
    tokens: number;
    content?: string;
  };
}

export interface RemoveContextCardMutationData {
  sessionId: string;
  cardId: string;
}

export interface AddFileDependencyMutationData {
  sessionId: string;
  fileDependency: {
    file_path: string;
    file_name: string;
    file_type: string;
    chunk_index: number;
    tokens: number;
    file_metadata?: Record<string, unknown>;
  };
}

export interface ContextCardMutationContext {
  previousCards: ContextCard[];
  optimisticCard?: ContextCard;
}

export interface FileDependencyMutationContext {
  previousFiles: FileItem[];
  optimisticFile?: FileItem;
}

// ============================================================================
// UI & STATE TYPES
// ============================================================================

export type TabType = 'chat' | 'context' | 'ideas' | 'solve';

export interface TabState {
  activeTab: TabType;
  refreshKeys: {
    chat: number;
    context: number;
    ideas: number;
  };
  tabHistory: TabType[];
}

// ============================================================================
// API RESPONSE TYPES
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

export interface CreateGitHubIssueResponse {
  success: boolean;
  github_url: string;
  message: string;
}

// ============================================================================
// SOLVER TYPES
// ============================================================================

export interface StartSolveRequest {
  issue_id: number;
  repo_url: string;
  branch_name?: string;
  ai_model_id?: number;
  ai_model_ids?: number[];
  small_change?: boolean;
  best_effort?: boolean;
  max_iterations?: number;
  max_cost?: number;
}

export interface StartSolveResponse {
  solve_session_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
}

export interface SolveRunOut {
  id: string;
  solve_id: string;
  model: string;
  temperature: number;
  max_edits: number;
  evolution: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  sandbox_id?: string;
  pr_url?: string;
  tests_passed?: boolean;
  loc_changed?: number;
  files_changed?: number;
  tokens?: number;
  latency_ms?: number;
  logs_url?: string;
  diagnostics?: Record<string, unknown>;
  trajectory_data?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
}

export interface SolveProgress {
  runs_total: number;
  runs_completed: number;
  runs_failed: number;
  runs_running: number;
  last_update?: string;
  message?: string;
}

export interface SolveStatusResponse {
  solve_session_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: SolveProgress;
  runs: SolveRunOut[];
  champion_run?: SolveRunOut;
  error_message?: string;
}

export interface CancelSolveResponse {
  solve_session_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  message: string;
}

// ============================================================================
// TRAJECTORY STREAMING TYPES
// ============================================================================

export interface TrajectoryMessage {
  role: string;
  content: string;
  extra?: Record<string, unknown>;
}

export interface TrajectoryInfo {
  exit_status?: string;
  submission?: string;
  model_stats?: {
    instance_cost?: number;
    api_calls?: number;
  };
  mini_version?: string;
  config?: {
    model?: {
      model_name?: string;
    };
  };
}

export interface TrajectoryData {
  info: TrajectoryInfo;
  messages: TrajectoryMessage[];
}

export interface TrajectoryUpdateEvent {
  messages: TrajectoryMessage[];
  info: TrajectoryInfo;
  message_count: number;
  new_message_start_index: number;
}

export interface TrajectoryStatusEvent {
  status: string;
}

export interface TrajectoryErrorEvent {
  message: string;
}

export interface SolveSessionOut {
  id: number;
  user_id: number;
  issue_id: number;
  ai_model_id?: number;
  swe_config_id?: number;
  status: string;
  repo_url: string;
  branch_name: string;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  trajectory_data?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SolveSessionStatsOut {
  session_id: number;
  status: string;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  total_edits: number;
  files_modified: number;
  lines_added: number;
  lines_removed: number;
  duration_seconds?: number;
  trajectory_steps: number;
  last_activity: string;
}

export interface RepositoryResponse {
  repositories: GitHubRepository[];
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

export interface FileAnalysisResponse {
  dependencies: FileContextItem[];
  total_tokens: number;
}

// ============================================================================
// LEGACY TYPE ALIASES (for backward compatibility)
// ============================================================================

// These aliases help with migration from old type names
export type SessionResponse = Session;
export type SessionContextResponse = SessionContext;
export type ChatMessageAPI = ChatMessage;
export type ChatMessageResponse = ChatMessage;
export type ContextCardResponse = ContextCard;
export type UserIssueResponse = UserIssue;
export type CreateSessionDaifuRequest = CreateSessionRequest;
export type SessionFileDependencyResponse = FileItem;
export type ExtractFileDependenciesRequest = {
  repo_url: string;
};
export type ExtractFileDependenciesResponse = {
  children: FileItem[];
};
