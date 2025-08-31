// ============================================================================
// FRONTEND-ONLY TYPES (not API-related)
// ============================================================================

import type { ContextCard, FileItem, User, GitHubRepository, GitHubBranch, SelectedRepository, ChatMessageAPI, SessionResponse, SessionContextResponse, UserIssueResponse, TabType, AgentStatus, CreateSessionMutationData, AddContextCardMutationData, RemoveContextCardMutationData, AddFileDependencyMutationData, ContextCardMutationContext, FileDependencyMutationContext } from './types/sessionTypes';

export interface IdeaItem {
  id: string;
  title: string;
  complexity: 'S' | 'M' | 'L' | 'XL';
  tests: number;
  confidence: number;
}

// Re-export types from sessionTypes for backward compatibility
export type { ContextCard, FileItem, User, GitHubRepository, GitHubBranch, SelectedRepository, ChatMessageAPI, SessionResponse, SessionContextResponse, UserIssueResponse, TabType, AgentStatus, CreateSessionMutationData, AddContextCardMutationData, RemoveContextCardMutationData, AddFileDependencyMutationData, ContextCardMutationContext, FileDependencyMutationContext };

// ============================================================================
// UI & STATE TYPES
// ============================================================================

export interface Message {
  id: string;
  content: string;
  timestamp: Date;
  sessionId: string;
}

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export type ProgressStep = 'DAifu' | 'Architect' | 'Test-Writer' | 'Coder';

export interface AuthState {
  user: User | null;
  sessionToken: string | null; // Changed from token to sessionToken
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthConfig {
  github_client_id: string;
  redirect_uri: string;
}

// ============================================================================
// TAB & SESSION MANAGEMENT
// ============================================================================

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






