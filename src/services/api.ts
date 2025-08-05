// API service for communicating with the backend
// This service provides complete coverage of all backend endpoints documented in context/APIDOCS.md
// State flow from frontend calls to database operations is documented in context/dbSchema.md
import { 
  SessionCreateRequest,
  SessionResponse,
  SessionContextResponse,
  UserIssueResponse
} from '../types';

// API endpoints use relative URLs to work with nginx proxy
const API_BASE_URL = '/api';

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

  // Session Management API Methods
  static async createSession(request: SessionCreateRequest): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });
    return this.handleResponse<SessionResponse>(response);
  }

  static async getSession(sessionId: string): Promise<SessionContextResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<SessionContextResponse>(response);
  }

  static async touchSession(sessionId: string): Promise<{success: boolean, session: SessionResponse}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/touch`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{success: boolean, session: SessionResponse}>(response);
  }

  static async getSessions(
    repoOwner?: string, 
    repoName?: string, 
    limit: number = 50
  ): Promise<SessionResponse[]> {
    const params = new URLSearchParams();
    if (repoOwner) params.append('repo_owner', repoOwner);
    if (repoName) params.append('repo_name', repoName);
    params.append('limit', limit.toString());

    const response = await fetch(`${API_BASE_URL}/daifu/sessions?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<SessionResponse[]>(response);
  }

  static async updateSessionTitle(sessionId: string, title: string): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/title`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ title }),
    });
    return this.handleResponse<SessionResponse>(response);
  }

  static async deleteSession(sessionId: string): Promise<{message: string}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{message: string}>(response);
  }

  static async getSessionStatistics(sessionId: string): Promise<{
    total_messages: number;
    total_tokens: number;
    total_cost: number;
    session_duration: number;
    user_issues_count?: number;
    file_embeddings_count?: number;
  }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/statistics`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{
      total_messages: number;
      total_tokens: number;
      total_cost: number;
      session_duration: number;
      user_issues_count?: number;
      file_embeddings_count?: number;
    }>(response);
  }

  // Chat API Methods
  static async sendChatMessage(request: ChatRequest, asyncMode: boolean = false): Promise<ChatResponse> {
    const url = asyncMode 
      ? `${API_BASE_URL}/chat/daifu/async`
      : `${API_BASE_URL}/chat/daifu`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });
    return this.handleResponse<ChatResponse>(response);
  }

  static async createIssueFromChat(request: ChatRequest): Promise<{
    success: boolean;
    issue: UserIssueResponse;
    message: string;
  }> {
    const response = await fetch(`${API_BASE_URL}/chat/create-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });
    return this.handleResponse<{
      success: boolean;
      issue: UserIssueResponse;
      message: string;
    }>(response);
  }

  // Issue Management API Methods
  static async createIssueWithContext(request: CreateIssueWithContextRequest): Promise<IssueCreationResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/from-session-enhanced`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });
    return this.handleResponse<IssueCreationResponse>(response);
  }

  static async getIssues(
    repoOwner?: string,
    repoName?: string,
    limit: number = 50
  ): Promise<UserIssueResponse[]> {
    const params = new URLSearchParams();
    if (repoOwner) params.append('repo_owner', repoOwner);
    if (repoName) params.append('repo_name', repoName);
    params.append('limit', limit.toString());

    const response = await fetch(`${API_BASE_URL}/issues?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<UserIssueResponse[]>(response);
  }

  static async getIssue(issueId: string): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<UserIssueResponse>(response);
  }

  static async updateIssue(issueId: string, updates: Partial<UserIssueResponse>): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(updates),
    });
    return this.handleResponse<UserIssueResponse>(response);
  }

  static async deleteIssue(issueId: string): Promise<{message: string}> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{message: string}>(response);
  }

  // File Dependencies API Methods
  static async analyzeFileDependencies(files: File[]): Promise<{
    dependencies: FileContextItem[];
    total_tokens: number;
  }> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const token = localStorage.getItem('auth_token');
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}/file-dependencies/analyze`, {
      method: 'POST',
      headers,
      body: formData,
    });
    return this.handleResponse<{
      dependencies: FileContextItem[];
      total_tokens: number;
    }>(response);
  }

  static async getFileDependencies(fileId: string): Promise<FileContextItem[]> {
    const response = await fetch(`${API_BASE_URL}/file-dependencies/${fileId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<FileContextItem[]>(response);
  }

  // Repository Management API Methods
  static async getRepositories(): Promise<{
    repositories: Array<{
      id: string;
      name: string;
      owner: string;
      description?: string;
      private: boolean;
      default_branch: string;
    }>;
  }> {
    const response = await fetch(`${API_BASE_URL}/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{
      repositories: Array<{
        id: string;
        name: string;
        owner: string;
        description?: string;
        private: boolean;
        default_branch: string;
      }>;
    }>(response);
  }

  static async getRepository(owner: string, name: string): Promise<{
    id: string;
    name: string;
    owner: string;
    description?: string;
    private: boolean;
    default_branch: string;
    branches: string[];
  }> {
    const response = await fetch(`${API_BASE_URL}/repositories/${owner}/${name}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{
      id: string;
      name: string;
      owner: string;
      description?: string;
      private: boolean;
      default_branch: string;
      branches: string[];
    }>(response);
  }

  // Legacy Auth Methods (for backward compatibility)
  static async login(credentials: {username: string, password: string}): Promise<{token: string}> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    });
    return this.handleResponse<{token: string}>(response);
  }

  static async logout(): Promise<void> {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      });
    } catch (error) {
      console.error('Logout request failed:', error);
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
    }
  }

  static async getAuthStatus(): Promise<{authenticated: boolean}> {
    const response = await fetch(`${API_BASE_URL}/auth/status`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<{authenticated: boolean}>(response);
  }

  static async validateState(state: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/validate-state`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ state }),
      });
      return response.ok;
    } catch (error) {
      console.error('State validation failed:', error);
      return false;
    }
  }
}