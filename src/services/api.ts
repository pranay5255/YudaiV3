// API service for communicating with the backend
import { 
  ChatSession, 
  ChatSessionStats, 
  ChatMessageAPI, 
  CreateIssueFromChatRequest,
  GitHubRepository,
  GitHubBranch
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatMessage {
  content: string;
  is_code: boolean;
}

export interface ChatRequest {
  conversation_id?: string; // Changed from session_id to match backend expectation
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

export interface CreateIssueFromSessionRequest {
  session_id: string;
  title: string;
  description?: string;
  priority?: string;
  use_code_inspector?: boolean;
  create_github_issue?: boolean;
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
  complexity_score?: string;
  estimated_hours?: number;
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

  static async createOrGetSession(
    repoOwner: string,
    repoName: string,
    repoBranch: string = 'main',
    title?: string,
    description?: string
  ): Promise<ChatSession> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        repo_owner: repoOwner,
        repo_name: repoName,
        repo_branch: repoBranch,
        title,
        description
      }),
    });

    return this.handleResponse<ChatSession>(response);
  }

  static async getSessionContext(sessionId: string): Promise<{
    session: ChatSession;
    messages: ChatMessageAPI[];
    context_cards: string[];
    repository_info?: Record<string, unknown>;
  }> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<{
      session: ChatSession;
      messages: ChatMessageAPI[];
      context_cards: string[];
      repository_info?: Record<string, unknown>;
    }>(response);
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
    useSampleData: boolean = true,
    sessionId?: string  // Optional session ID for enhanced creation
  ): Promise<IssueCreationResponse> {
    // If session ID is provided, use the enhanced session-based endpoint
    if (sessionId) {
      const sessionRequest: CreateIssueFromSessionRequest = {
        session_id: sessionId,
        title: request.title,
        description: request.description,
        priority: request.priority || 'medium',
        use_code_inspector: true,
        create_github_issue: false  // Default to false for safety
      };
      
      try {
        const userIssue = await this.createIssueFromSessionEnhanced(sessionRequest);
        
        // Convert UserIssueResponse to IssueCreationResponse format
        const issueCreationResponse: IssueCreationResponse = {
          success: true,
          preview_only: false,
          github_preview: {
            title: userIssue.title,
            body: userIssue.issue_text_raw,
            labels: ['yudai-assistant', 'session-generated'],
            assignees: [],
            repository_info: userIssue.repo_owner && userIssue.repo_name ? {
              owner: userIssue.repo_owner,
              name: userIssue.repo_name
            } : undefined,
            metadata: {
              chat_messages_count: 0, // Would need to be calculated from session
              file_context_count: 0,
              total_tokens: userIssue.tokens_used,
              generated_at: userIssue.created_at,
              generation_method: 'session_enhanced'
            }
          },
          user_issue: userIssue,
          message: `Issue created successfully with ID: ${userIssue.issue_id}`
        };
        
        return issueCreationResponse;
      } catch (error) {
        // Fall back to original method if enhanced creation fails
        console.warn('Enhanced session-based issue creation failed, falling back to original method:', error);
      }
    }
    
    // Original implementation for non-session-based creation
    const response = await fetch(`${API_BASE_URL}/issues/create-with-context?preview_only=${previewOnly}&use_sample_data=${useSampleData}`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<IssueCreationResponse>(response);
  }

  static async createIssueFromSessionEnhanced(
    request: CreateIssueFromSessionRequest
  ): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/from-session-enhanced`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(request),
    });

    return this.handleResponse<UserIssueResponse>(response);
  }

  static async createGitHubIssueFromSession(
    sessionId: string,
    title: string,
    description?: string,
    priority: string = 'medium'
  ): Promise<UserIssueResponse> {
    const request: CreateIssueFromSessionRequest = {
      session_id: sessionId,
      title,
      description,
      priority,
      use_code_inspector: true,
      create_github_issue: true  // This will create the actual GitHub issue
    };

    return this.createIssueFromSessionEnhanced(request);
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
}