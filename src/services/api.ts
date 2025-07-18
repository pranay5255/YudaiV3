// API service for communicating with the backend
import { 
  ChatSession, 
  ChatSessionStats, 
  ChatMessageAPI, 
  CreateIssueFromChatRequest,
  GitHubRepository,
  GitHubBranch
} from '../types';

const API_BASE_URL = 'http://localhost:8000';

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

    return this.handleResponse<ChatSession[]>(response);
  }

  static async getSessionMessages(sessionId: string): Promise<ChatMessageAPI[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/chat/sessions/${sessionId}/messages`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<ChatMessageAPI[]>(response);
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

  // GitHub Services
  /* eslint-disable @typescript-eslint/no-explicit-any */
  static async getRepositories(): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any[]>(response);
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

    return this.handleResponse<any[]>(response);
  }

  // File Dependencies Services
  static async getFileDependencies(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/filedeps/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<any>(response);
  }

  static async extractFileDependencies(repositoryUrl: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/filedeps/extract`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ repository_url: repositoryUrl }),
    });

    return this.handleResponse<any>(response);
  }
} 