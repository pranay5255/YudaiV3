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

