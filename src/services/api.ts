// API service for communicating with the backend
// This service provides complete coverage of all backend endpoints documented in context/APIDOCS.md
// State flow from frontend calls to database operations is documented in context/dbSchema.md
import { 
  SessionCreateRequest,
  SessionResponse,
  SessionContextResponse,
  UserIssueResponse
} from '../types';

// API endpoints use the full VITE_API_URL (includes /api prefix)
const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app/api');

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
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<SessionResponse>(response);
  }

  static async getSession(sessionId: string): Promise<SessionContextResponse> {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<SessionContextResponse>(response);
  }

  static async touchSession(sessionId: string): Promise<{success: boolean, session: SessionResponse}> {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/touch`, {
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

    const response = await fetch(`${API_BASE_URL}/sessions?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<SessionResponse[]>(response);
  }

  static async updateSessionTitle(sessionId: string, title: string): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/title`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ title }),
    });

    return this.handleResponse<SessionResponse>(response);
  }

  static async deleteSession(sessionId: string): Promise<{message: string}> {
    const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
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
    const response = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/statistics`, {
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
    const params = new URLSearchParams();
    if (asyncMode) {
      params.append('async_mode', 'true');
    }
    
    const response = await fetch(`${API_BASE_URL}/chat/daifu?${params}`, {
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

  // Removed WebSocket connection - using HTTP API only

  // Auth Methods
  static async login(credentials: {username: string, password: string}): Promise<{token: string}> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(credentials),
    });

    return this.handleResponse<{token: string}>(response);
  }

  static async logout(): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    if (response.ok) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
    }

    return this.handleResponse<void>(response);
  }

  static async getAuthStatus(): Promise<{authenticated: boolean}> {
    const response = await fetch(`${API_BASE_URL}/auth/status`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{authenticated: boolean}>(response);
  }

  // State validation endpoint
  static async validateState(state: string): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}/auth/validate-state`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ state })
    });
    
    if (!response.ok) {
      return false;
    }
    
    return response.json().then(data => data.valid);
  }
}