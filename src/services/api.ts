// API service for communicating with the backend
// This service provides complete coverage of all backend endpoints documented in context/APIDOCS.md
// State flow from frontend calls to database operations is documented in context/dbSchema.md
import { UserIssueResponse } from '../types';
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  ValidateSessionResponse,
  LogoutRequest,
  LogoutResponse,
  LoginUrlResponse,
  ChatRequest,
  ChatResponse,
  CreateIssueFromChatResponse,
  FileContextItem,
  CreateIssueWithContextRequest,
  IssueCreationResponse,
  CreateGitHubIssueResponse,
  GitHubRepositoryAPI,
  GitHubBranchAPI,
  RepositoryResponse,
  RepositoryDetailsResponse,
  FileAnalysisResponse,
  ExtractFileDependenciesRequest,
  ExtractFileDependenciesResponse,
  CreateSessionDaifuRequest,
  SessionResponse,
  SessionContextResponse,
  CreateChatMessageRequest,
  ChatMessageResponse,
  ContextCardResponse,
  CreateContextCardRequest,
  CreateFileEmbeddingRequest,
  FileEmbeddingResponse,
} from '../types/api';

// API base URL from environment or fallback to relative path
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiService {
  private static getAuthHeaders(sessionToken?: string): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    // Use session token from parameter or try to get from localStorage
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    } else {
      // Try to get session token from localStorage
      const tokenFromStorage = localStorage.getItem('session_token');
      if (tokenFromStorage) {
        headers['Authorization'] = `Bearer ${tokenFromStorage}`;
      }
    }
    
    return headers;
  }

  private static async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      if (response.status === 401) {
        // Redirect to login instead of clearing localStorage
        window.location.href = '/auth/login';
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

  // Authentication API Methods
  static async createAuthSession(request: CreateSessionRequest): Promise<CreateSessionResponse> {
    const response = await fetch(`/auth/api/create-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    return this.handleResponse<CreateSessionResponse>(response);
  }

  // Session Management API Methods
  static async createSession(request: CreateSessionDaifuRequest, sessionToken?: string): Promise<SessionResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<SessionResponse>(response);
  }

  static async getSessionContext(sessionId: string, sessionToken?: string): Promise<SessionContextResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<SessionContextResponse>(response);
  }

  static async validateSessionToken(sessionToken: string): Promise<ValidateSessionResponse> {
    const response = await fetch(`/auth/api/user?session_token=${sessionToken}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return this.handleResponse<ValidateSessionResponse>(response);
  }

  static async logout(sessionToken: string): Promise<LogoutResponse> {
    const response = await fetch(`/auth/api/logout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_token: sessionToken } as LogoutRequest),
    });
    return this.handleResponse<LogoutResponse>(response);
  }

  static async getLoginUrl(): Promise<LoginUrlResponse> {
    const response = await fetch(`/auth/api/login`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return this.handleResponse<LoginUrlResponse>(response);
  }

  // Chat API Methods
  static async sendChatMessage(request: ChatRequest, sessionToken?: string): Promise<ChatResponse> {
    // Validate session_id is required
    if (!request.session_id?.trim()) {
      throw new Error('session_id is required and cannot be empty');
    }

    const response = await fetch(`${API_BASE_URL}/chat/daifu`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<ChatResponse>(response);
  }

  static async createIssueFromChat(request: ChatRequest, sessionToken?: string): Promise<CreateIssueFromChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat/create-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken), 
      body: JSON.stringify(request),
    });
    return this.handleResponse<CreateIssueFromChatResponse>(response);
  }

  // Issue Management API Methods
  static async createIssueWithContext(request: CreateIssueWithContextRequest, githubToken?: string): Promise<IssueCreationResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/from-session-enhanced`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<IssueCreationResponse>(response);
  }

  static async getIssues(
    repoOwner?: string,
    repoName?: string,
    limit: number = 50,
    githubToken?: string
  ): Promise<UserIssueResponse[]> {
    const params = new URLSearchParams();
    if (repoOwner) params.append('repo_owner', repoOwner);
    if (repoName) params.append('repo_name', repoName);
    params.append('limit', limit.toString());

    const response = await fetch(`${API_BASE_URL}/issues?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<UserIssueResponse[]>(response);
  }

  static async getIssue(issueId: string, githubToken?: string): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<UserIssueResponse>(response);
  }

  static async updateIssue(issueId: string, updates: Partial<UserIssueResponse>, githubToken?: string): Promise<UserIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'PUT',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify(updates),
    });
    return this.handleResponse<UserIssueResponse>(response);
  }

  static async deleteIssue(issueId: string, githubToken?: string): Promise<{message: string}> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<{message: string}>(response);
  }

  // File Dependencies API Methods
  static async analyzeFileDependencies(files: File[], githubToken?: string): Promise<FileAnalysisResponse> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const headers: HeadersInit = {};
    if (githubToken) {
      headers['Authorization'] = `Bearer ${githubToken}`;
    } else {
      // Try to get github token from URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get('github_token');
      if (tokenFromUrl) {
        headers['Authorization'] = `Bearer ${tokenFromUrl}`;
      }
    }

    const response = await fetch(`${API_BASE_URL}/file-dependencies/analyze`, {
      method: 'POST',
      headers,
      body: formData,
    });
    return this.handleResponse<FileAnalysisResponse>(response);
  }

  static async getFileDependencies(fileId: string, githubToken?: string): Promise<FileContextItem[]> {
    const response = await fetch(`${API_BASE_URL}/file-dependencies/${fileId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<FileContextItem[]>(response);
  }

  // Repository Management API Methods
  static async getRepositories(githubToken?: string): Promise<RepositoryResponse> {
    const response = await fetch(`${API_BASE_URL}/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<RepositoryResponse>(response);
  }

  static async getRepository(owner: string, name: string, githubToken?: string): Promise<RepositoryDetailsResponse> {
    const response = await fetch(`${API_BASE_URL}/repositories/${owner}/${name}`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<RepositoryDetailsResponse>(response);
  }

  static async createGitHubIssueFromUserIssue(issueId: string, githubToken?: string): Promise<CreateGitHubIssueResponse> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}/create-github-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<CreateGitHubIssueResponse>(response);
  }

  static async extractFileDependencies(repoUrl: string, githubToken?: string): Promise<ExtractFileDependenciesResponse> {
    const response = await fetch(`${API_BASE_URL}/filedeps/extract`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify({ repo_url: repoUrl } as ExtractFileDependenciesRequest),
    });
    return this.handleResponse<ExtractFileDependenciesResponse>(response);
  }

  static async getRepositoryBranches(owner: string, repo: string, githubToken?: string): Promise<GitHubBranchAPI[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/branches`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<GitHubBranchAPI[]>(response);
  }

  static async getUserRepositories(githubToken?: string): Promise<GitHubRepositoryAPI[]> {
    const response = await fetch(`${API_BASE_URL}/github/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<GitHubRepositoryAPI[]>(response);
  }

  // Chat Messages CRUD
  static async addChatMessage(
    sessionId: string, 
    request: CreateChatMessageRequest, 
    sessionToken?: string
  ): Promise<ChatMessageResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<ChatMessageResponse>(response);
  }

  static async getChatMessages(
    sessionId: string, 
    limit: number = 100, 
    sessionToken?: string
  ): Promise<ChatMessageResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages?limit=${limit}`, {
      method: 'GET',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<ChatMessageResponse[]>(response);
  }

  static async deleteChatMessage(
    sessionId: string, 
    messageId: string, 
    sessionToken?: string
  ): Promise<{success: boolean, message: string}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/messages/${messageId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<{success: boolean, message: string}>(response);
  }

  // Context Cards CRUD
  static async addContextCard(
    sessionId: string, 
    request: CreateContextCardRequest, 
    sessionToken?: string
  ): Promise<ContextCardResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<ContextCardResponse>(response);
  }

  static async getContextCards(
    sessionId: string, 
    sessionToken?: string
  ): Promise<ContextCardResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards`, {
      method: 'GET',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<ContextCardResponse[]>(response);
  }

  static async deleteContextCard(
    sessionId: string, 
    cardId: number, 
    sessionToken?: string
  ): Promise<{success: boolean, message: string}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/context-cards/${cardId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<{success: boolean, message: string}>(response);
  }

  // File Dependencies CRUD
  static async addFileDependency(
    sessionId: string, 
    request: CreateFileEmbeddingRequest, 
    sessionToken?: string
  ): Promise<FileEmbeddingResponse> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-dependencies`, {
      method: 'POST',
      headers: this.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<FileEmbeddingResponse>(response);
  }

  static async getFileDependenciesSession(
    sessionId: string, 
    sessionToken?: string
  ): Promise<FileEmbeddingResponse[]> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-dependencies`, {
      method: 'GET',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<FileEmbeddingResponse[]>(response);
  }

  static async deleteFileDependency(
    sessionId: string, 
    fileId: number, 
    sessionToken?: string
  ): Promise<{success: boolean, message: string}> {
    const response = await fetch(`${API_BASE_URL}/daifu/sessions/${sessionId}/file-dependencies/${fileId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(sessionToken),
    });
    return this.handleResponse<{success: boolean, message: string}>(response);
  }
}