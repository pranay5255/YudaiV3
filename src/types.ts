export interface ContextCard {
  id: string;
  title: string;
  description: string;
  tokens: number;
  source: 'chat' | 'file-deps' | 'upload';
}

export interface IdeaItem {
  id: string;
  title: string;
  complexity: 'S' | 'M' | 'L' | 'XL';
  tests: number;
  confidence: number;
}

// Updated to match the database schema from models.py
export interface FileItem {
  id: string;
  name: string; // file/directory name
  path?: string; // full path (optional for frontend)
  type: 'INTERNAL' | 'EXTERNAL'; // matches FileType enum from models.py
  tokens: number; // int
  Category: string; // category classification
  isDirectory: boolean; // matches is_directory from database
  children?: FileItem[];
  expanded?: boolean; // frontend-only state
  content?: string; // optional file content
  content_size?: number; // optional content size
}

// API response type for the filedeps endpoint
export interface FileItemAPIResponse {
  id?: string;
  name?: string;
  path?: string;
  type?: string; // can be any string from API
  tokens?: number;
  category?: string;
  Category?: string;
  isDirectory?: boolean;
  children?: FileItemAPIResponse[];
}

export interface Message {
  id: string;
  content: string;
  isCode: boolean;
  timestamp: Date;
}

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export type ProgressStep = 'DAifu' | 'Architect' | 'Test-Writer' | 'Coder';
export type TabType = 'chat' | 'file-deps' | 'context' | 'ideas';

// Auth types
export interface User {
  id: number; // Changed from string to number to match backend
  github_username: string; // Changed from username to match backend
  github_user_id: string; // Changed from github_id to match backend
  email?: string;
  display_name?: string; // Added display_name field from backend
  avatar_url?: string;
  created_at: string;
  last_login?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthConfig {
  github_client_id: string;
  redirect_uri: string;
}

// Tab management with session persistence
export interface TabState {
  activeTab: TabType;
  refreshKeys: {
    chat: number;
    'file-deps': number;
    context: number;
    ideas: number;
  };
  tabHistory: TabType[];
}

// GitHub types
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
}

export interface GitHubBranch {
  name: string;
  commit: {
    sha: string;
    url: string;
  };
  protected: boolean;
}

export interface SelectedRepository {
  repository: GitHubRepository;
  branch: string;
}

// Chat API types
export interface ChatSession {
  id: string;
  title?: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface ChatSessionStats {
  total_messages: number;
  total_tokens: number;
  total_cost: number;
}

export interface ChatMessageAPI {
  id: number;
  message_id: string;
  message_text: string;
  sender_type: 'user' | 'assistant' | 'system';
  role: 'user' | 'assistant' | 'system';
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

export interface CreateIssueFromChatRequest {
  session_id: string;
  title: string;
  description?: string;
  repository_url?: string;
}

// Enhanced Session Types for comprehensive state management
export interface SessionCreateRequest {
  repo_owner: string;
  repo_name: string;
  repo_branch: string;
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
  messages: ChatMessageAPI[];
  context_cards: string[];  // Array of context card IDs
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

// File embedding response interface to match backend
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

// User issue response interface to match backend
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

// Real-time update types for Server-Sent Events
export interface SessionUpdateEvent {
  type: 'message' | 'context_card' | 'session_update' | 'agent_status' | 'repository_update';
  session_id: string;
  data: unknown;
  timestamp: string;
}

export interface AgentStatus {
  type: 'daifu' | 'architect' | 'coder' | 'tester';
  status: 'idle' | 'processing' | 'completed' | 'error';
  progress?: number;
  message?: string;
  started_at?: string;
  completed_at?: string;
}

// Comprehensive Session State Interface
export interface SessionState {
  // Core session data
  sessionId: string | null;
  session: SessionResponse | null;
  
  // Repository context
  repository: GitHubRepository | null;
  branch: string;
  repositoryInfo: {
    owner: string;
    name: string;
    branch: string;
    full_name: string;
    html_url: string;
  } | null;
  
  // Chat data
  messages: ChatMessageAPI[];
  isLoadingMessages: boolean;
  messageRefreshKey: number;
  
  // Context management
  contextCards: ContextCard[];
  fileContext: FileItem[];
  totalTokens: number;
  
  // Issue management
  userIssues: UserIssueResponse[];
  currentIssue: UserIssueResponse | null;
  
  // Agent orchestration
  agentStatus: AgentStatus;
  agentHistory: AgentStatus[];
  
  // Session statistics
  statistics: {
    total_messages: number;
    total_tokens: number;
    total_cost: number;
    session_duration: number;
  };
  
  // UI state
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date;
  connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
}

// GitHub Issue Context Structure
export interface GitHubIssueContext {
  conversation: {
    messages: Message[];
    contextCards: ContextCard[];
  };
  fileDependencies: {
    cards: ContextCard[];
    totalTokens: number;
  };
  summary: {
    totalContextCards: number;
    totalTokens: number;
    conversationLength: number;
    filesIncluded: number;
  };
}

