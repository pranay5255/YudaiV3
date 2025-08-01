// API service for communicating with the backend
// This service provides complete coverage of all backend endpoints documented in context/APIDOCS.md
// State flow from frontend calls to database operations is documented in context/dbSchema.md
import { 
  ChatSession, 
  ChatSessionStats, 
  ChatMessageAPI, 
  CreateIssueFromChatRequest,
  GitHubRepository,
  GitHubBranch
} from '../types';

// API endpoints use the full VITE_API_URL (includes /api prefix)
const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app/api');

export interface ChatMessage {
  content: string;
  is_code: boolean;
}

export interface ChatRequest {
  conversation_id?: string; // Fixed: backend expects conversation_id, not session_id
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

// Add new interfaces for issue creation with context
export interface FileContextItem {
  id: string;
  name: string;
  type: string;
  tokens: number;
  category: string;
  path?: string;
}

export interface ChatContextMessage {
  id: string;
  content: string;
  isCode: boolean;
  timestamp: string;
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
  user_issue?: UserIssueResponse;
  message: string;
}

export interface UserIssueResponse {
  id: number;
  issue_id: string;
  user_id: number;
  title: string;
  description?: string;
  issue_text_raw: string;
  issue_steps?: string[];
  conversation_id?: string;
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

export class ApiService {
  private static getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('auth_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }

  private static async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      if (response.status === 401) {
        // Token expired or invalid - redirect to login
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_data');
        window.location.reload();
        throw new Error('Authentication required');
      }
      
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        // If we can't parse error JSON, use the default message
      }
      
      throw new Error(errorMessage);
    }

    return response.json();
  }

  // Daifu Chat Services
  static async sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/daifu`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<ChatResponse>(response);
  }

  static async getChatSessions(): Promise<ChatSession[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    const result = await this.handleResponse<{ sessions: ChatSession[] }>(response);
    return result.sessions; // Fixed: backend returns { sessions: [...] }
  }

  static async getSessionMessages(sessionId: string): Promise<ChatMessageAPI[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions/${sessionId}/messages`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    const result = await this.handleResponse<{ messages: ChatMessageAPI[] }>(response);
    return result.messages; // Fixed: backend returns { messages: [...] }
  }

  static async getSessionStatistics(sessionId: string): Promise<ChatSessionStats> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions/${sessionId}/statistics`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<ChatSessionStats>(response);
  }

  static async updateSessionTitle(sessionId: string, title: string): Promise<{ success: boolean }> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions/${sessionId}/title`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ title }),
    });

    return this.handleResponse<{ success: boolean }>(response);
  }

  static async deactivateSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{ success: boolean }>(response);
  }

  static async createIssueFromChat(request: CreateIssueFromChatRequest): Promise<{ issue_id: string; github_issue_url?: string }> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/create-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<{ issue_id: string; github_issue_url?: string }>(response);
  }

  // GitHub Services - Deprecated: Use getUserRepositories() instead
  /* eslint-disable @typescript-eslint/no-explicit-any */
  static async getRepositories(): Promise<any[]> {
    console.warn('getRepositories() is deprecated. Use getUserRepositories() instead.');
    return this.getUserRepositories();
  }

  static async getRepository(owner: string, repo: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any>(response);
  }

  static async createRepositoryIssue(owner: string, repo: string, issueData: any): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/issues`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(issueData),
    });

    return this.handleResponse<any>(response);
  }

  static async getRepositoryIssues(owner: string, repo: string): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/issues`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any[]>(response);
  }

  // GitHub API Services
  static async getUserRepositories(): Promise<GitHubRepository[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<GitHubRepository[]>(response);
  }

  static async getRepositoryBranches(owner: string, repo: string): Promise<GitHubBranch[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/branches`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<GitHubBranch[]>(response);
  }

  static async searchRepositories(query: string): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/github/search/repositories?q=${encodeURIComponent(query)}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    const result = await this.handleResponse<{ repositories: any[] }>(response);
    return result.repositories || []; // Fixed: handle potential structure difference
  }

  // File Dependencies Services
  static async getFileDependencies(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/filedeps/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any>(response);
  }

  static async extractFileDependencies(repositoryUrl: string, maxFileSize?: number): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/filedeps/extract`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ 
        repo_url: repositoryUrl,
        max_file_size: maxFileSize || 30000
      }),
    });

    return this.handleResponse<any>(response);
  }

  // Issue Services
  static async createIssueWithContext(
    request: CreateIssueWithContextRequest, 
    previewOnly: boolean = false,
    useSampleData: boolean = true
  ): Promise<IssueCreationResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/create-with-context?preview_only=${previewOnly}&use_sample_data=${useSampleData}`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<IssueCreationResponse>(response);
  }

  static async createGitHubIssueFromUserIssue(issueId: string): Promise<{ success: boolean; github_url: string; message: string }> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}/create-github-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{ success: boolean; github_url: string; message: string }>(response);
  }

  static async getUserIssues(filters?: {
    status?: string;
    priority?: string;
    repo_owner?: string;
    repo_name?: string;
    limit?: number;
  }): Promise<UserIssueResponse[]> {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) {
          params.append(key, value.toString());
        }
      });
    }
    
    const response = await fetch(`${API_BASE_URL}/issues/?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<UserIssueResponse[]>(response);
  }

  static async getUserIssue(issueId: string): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<UserIssueResponse>(response);
  }

  static async getRepositoryByUrl(repoUrl: string): Promise<any | null> {
    const url = `${API_BASE_URL}/filedeps/repositories?repo_url=${encodeURIComponent(repoUrl)}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    if (response.status === 404) {
      return null;
    }
    return this.handleResponse<any>(response);
  }

  static async getRepositoryFiles(repositoryId: number): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/filedeps/repositories/${repositoryId}/files`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any[]>(response);
  }

  // Enhanced Session Management Services using unused API endpoints
  
  /**
   * Creates a new session using the dedicated session creation endpoint
   * This replaces the legacy createOrGetSession method
   * @param repoOwner - Repository owner username
   * @param repoName - Repository name
   * @param repoBranch - Repository branch (defaults to 'main')
   * @param title - Optional session title
   * @param description - Optional session description
   * @returns Promise<SessionResponse> - Complete session information
   */
  static async createSession(
    repoOwner: string,
    repoName: string,
    repoBranch: string = 'main',
    title?: string,
    description?: string
  ): Promise<import('../types').SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title: title || `Session for ${repoOwner}/${repoName}`,
        description: description || `Working session for ${repoOwner}/${repoName} on ${repoBranch} branch`
      }),
    });

    return this.handleResponse<import('../types').SessionResponse>(response);
  }

  /**
   * Gets comprehensive session context including messages, context cards, and repository info
   * @param sessionId - Session ID to retrieve context for
   * @returns Promise<SessionContextResponse> - Complete session context
   */
  static async getSessionContextById(sessionId: string): Promise<import('../types').SessionContextResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<import('../types').SessionContextResponse>(response);
  }

  /**
   * Updates session activity timestamp - used for real-time session management
   * @param sessionId - Session ID to touch
   * @returns Promise<{success: boolean}> - Operation result
   */
  static async touchSession(sessionId: string): Promise<{success: boolean}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/touch`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{success: boolean}>(response);
  }

  /**
   * Gets all user sessions with optional filtering by repository
   * @param repoOwner - Optional repository owner filter
   * @param repoName - Optional repository name filter
   * @returns Promise<SessionResponse[]> - Array of user sessions
   */
  static async getUserSessions(
    repoOwner?: string, 
    repoName?: string
  ): Promise<import('../types').SessionResponse[]> {
    const params = new URLSearchParams();
    if (repoOwner) params.append('repo_owner', repoOwner);
    if (repoName) params.append('repo_name', repoName);
    
    const response = await fetch(`${API_BASE_URL}/daifu/sessions?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<import('../types').SessionResponse[]>(response);
  }

  /**
   * Legacy method for backward compatibility - now uses new session creation
   * @deprecated Use createSession instead
   */
  static async createOrGetSession(
    repoOwner: string,
    repoName: string,
    repoBranch: string = 'main',
    title?: string
  ): Promise<ChatSession> {
    console.warn('createOrGetSession is deprecated. Use createSession instead.');
    
    // Try to get existing session first
    const existingSessions = await this.getUserSessions(repoOwner, repoName);
    const activeSession = existingSessions.find(session => 
      session.is_active && session.repo_branch === repoBranch
    );

    if (activeSession) {
      // Convert SessionResponse to ChatSession for backward compatibility
      return {
        id: activeSession.id,
        title: activeSession.title,
        created_at: activeSession.created_at,
        updated_at: activeSession.updated_at,
        is_active: activeSession.is_active
      };
    }

    // Create new session
    const newSession = await this.createSession(repoOwner, repoName, repoBranch, title);
    
    // Convert SessionResponse to ChatSession for backward compatibility
    return {
      id: newSession.id,
      title: newSession.title,
      created_at: newSession.created_at,
      updated_at: newSession.updated_at,
      is_active: newSession.is_active
    };
  }

  /**
   * Legacy getSessionContext method - now uses enhanced session context endpoint
   * @deprecated Use getSessionContextById instead for full context
   */
  static async getSessionContext(sessionId: string): Promise<{
    session: ChatSession;
    messages: ChatMessageAPI[];
    context_cards: string[];
    repository_info?: Record<string, unknown>;
  }> {
    console.warn('getSessionContext is deprecated. Use getSessionContextById for enhanced context.');
    
    try {
      // Try to get enhanced context first
      const enhancedContext = await this.getSessionContextById(sessionId);
      
      return {
        session: {
          id: enhancedContext.session.id,
          title: enhancedContext.session.title,
          created_at: enhancedContext.session.created_at,
          updated_at: enhancedContext.session.updated_at,
          is_active: enhancedContext.session.is_active
        },
        messages: enhancedContext.messages,
        context_cards: enhancedContext.context_cards,
        repository_info: {
          ...enhancedContext.repository_info,
          ...enhancedContext.statistics
        }
      };
    } catch (error) {
      // Fallback to legacy implementation
      console.warn('Enhanced context failed, falling back to legacy:', error);
      
      const [sessions, messages, sessionStats] = await Promise.all([
        this.getChatSessions(),
        this.getSessionMessages(sessionId),
        this.getSessionStatistics(sessionId)
      ]);

      const session = sessions.find(s => s.id === sessionId);
      if (!session) {
        throw new Error('Session not found');
      }

      return {
        session,
        messages,
        context_cards: [],
        repository_info: {
          session_id: sessionId,
          session_title: session.title,
          created_at: session.created_at,
          updated_at: session.updated_at,
          is_active: session.is_active,
          ...sessionStats
        }
      };
    }
  }

  // Authentication Services
  static async getAuthStatus(): Promise<{ authenticated: boolean; user?: any }> {
    const response = await fetch(`${API_BASE_URL}/auth/status`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{ authenticated: boolean; user?: any }>(response);
  }

  static async getUserProfile(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/auth/profile`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any>(response);
  }

  static async logout(): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    const result = await this.handleResponse<{ success: boolean; message: string }>(response);
    
    // Clear local storage on successful logout
    if (result.success) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
    }

    return result;
  }

  // NEW: Additional backend endpoints not previously implemented in frontend

  /**
   * Establishes WebSocket connection for real-time session updates
   * @param sessionId - Session ID to listen for updates
   * @returns WebSocket - WebSocket connection for real-time updates
   */
  static createSessionWebSocket(sessionId: string, token: string | null): WebSocket {
    // Get the base URL without /api prefix
    const baseUrl = import.meta.env.VITE_API_URL || 
      (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app');
    
    // Remove /api prefix if present
    const cleanBaseUrl = baseUrl.replace('/api', '');
    
    // Convert to WebSocket URL
    const wsUrl = cleanBaseUrl.replace('http', 'ws').replace('https', 'wss');
    
    const url = new URL(`${wsUrl}/daifu/sessions/${sessionId}/ws`);
    
    if (token) {
      url.searchParams.append('token', token);
    }
    
    return new WebSocket(url.toString());
  }



  /**
   * Sends enhanced chat message with session context (WebSocket-enabled)
   * Uses the v2 endpoint that supports real-time WebSocket broadcasting
   * @param request - Enhanced chat request with session context
   * @returns Promise<ChatResponse> - Enhanced chat response
   */
  static async sendEnhancedChatMessage(request: {
    session_id: string;
    message: ChatMessage;
    context_cards?: string[];
    file_context?: string[];
  }): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/daifu/v2`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        conversation_id: request.session_id,
        message: request.message,
        context_cards: request.context_cards || [],
        file_context: request.file_context || []
      }),
    });

    return this.handleResponse<ChatResponse>(response);
  }

  // Additional GitHub Endpoints
  static async getRepositoryPulls(owner: string, repo: string, state: string = 'open'): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/pulls?state=${state}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any[]>(response);
  }

  static async getRepositoryCommits(owner: string, repo: string, branch: string = 'main'): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/commits?branch=${branch}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any[]>(response);
  }

  // Additional Issue Endpoints
  static async createUserIssue(request: any): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<UserIssueResponse>(response);
  }

  static async createIssueFromChatRequest(chatRequest: any): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/from-chat`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(chatRequest),
    });

    return this.handleResponse<UserIssueResponse>(response);
  }

  static async getIssueStatistics(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/issues/statistics`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any>(response);
  }

  // Auth Configuration Endpoint
  static async getAuthConfig(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/auth/config`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }, // No auth required for config
    });

    return this.handleResponse<any>(response);
  }

  /**
   * Global health check for API and real-time connections
   * @returns Promise<{api: boolean, realtime: boolean}> - Service health status
   */
  static async checkHealth(): Promise<{api: boolean, realtime: boolean}> {
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const health = await this.handleResponse<{api: boolean, realtime: boolean}>(response);
      return health;
    } catch {
      return { api: false, realtime: false };
    }
  }
}