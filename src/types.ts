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
  id: string;
  username: string;
  email?: string;
  avatar_url?: string;
  github_id?: string;
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
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: string;
  is_code: boolean;
}

export interface CreateIssueFromChatRequest {
  session_id: string;
  title: string;
  description?: string;
  repository_url?: string;
}

export type IssueCategory =
  | 'Bug-fix'
  | 'Add-library'
  | 'add-tests(pytest)'
  | 'add-tests(docker)'
  | 'new-feature-scaffold'
  | 'refactor'
  | 'docs update'
  | 'context-update(md files)'
  | 'containerisation'
  | 'database-design(sqlAlchemy+pydantic)'
  | 'type-setting(pydantic)'
  | 'type-setting(typescript)';

export interface IssueConfig {
  repoOwner: string;
  repoName: string;
  branch: string;
  categories: IssueCategory[];
}

