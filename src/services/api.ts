// API service for communicating with the backend
// This service provides complete coverage of all backend endpoints documented in context/APIDOCS.md
// State flow from frontend calls to database operations is documented in context/dbSchema.md
import { 
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
  private static getAuthHeaders(githubToken?: string): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    // Use github token from parameter or try to get from URL
    if (githubToken) {
      headers['Authorization'] = `Bearer ${githubToken}`;
    } else {
      // Try to get github token from URL parameters (for OAuth callback)
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get('github_token');
      if (tokenFromUrl) {
        headers['Authorization'] = `Bearer ${tokenFromUrl}`;
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
  static async createSession(githubToken: string): Promise<{
    session_token: string;
    expires_at: string;
    user: {
      id: number;
      github_username: string;
      github_user_id: string;
      email: string;
      display_name: string;
      avatar_url: string;
      created_at: string;
      last_login: string;
    };
  }> {
    const response = await fetch(`${API_BASE_URL}/auth/api/create-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ github_token: githubToken }),
    });
    return this.handleResponse<{
      session_token: string;
      expires_at: string;
      user: {
        id: number;
        github_username: string;
        github_user_id: string;
        email: string;
        display_name: string;
        avatar_url: string;
        created_at: string;
        last_login: string;
      };
    }>(response);
  }

  static async validateSessionToken(sessionToken: string): Promise<{
    id: number;
    github_username: string;
    github_id: string;
    display_name: string;
    email: string;
    avatar_url: string;
  }> {
    const response = await fetch(`${API_BASE_URL}/auth/api/user?session_token=${sessionToken}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return this.handleResponse<{
      id: number;
      github_username: string;
      github_id: string;
      display_name: string;
      email: string;
      avatar_url: string;
    }>(response);
  }

  static async logout(sessionToken: string): Promise<{success: boolean; message: string}> {
    const response = await fetch(`${API_BASE_URL}/auth/api/logout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_token: sessionToken }),
    });
    return this.handleResponse<{success: boolean; message: string}>(response);
  }

  static async getLoginUrl(): Promise<{login_url: string}> {
    const response = await fetch(`${API_BASE_URL}/auth/api/login`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return this.handleResponse<{login_url: string}>(response);
  }

  // Chat API Methods
  static async sendChatMessage(request: ChatRequest, asyncMode: boolean = false, githubToken?: string): Promise<ChatResponse> {
    const url = asyncMode 
      ? `${API_BASE_URL}/chat/daifu/async`
      : `${API_BASE_URL}/chat/daifu`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<ChatResponse>(response);
  }

  static async createIssueFromChat(request: ChatRequest, githubToken?: string): Promise<{
    success: boolean;
    issue: UserIssueResponse;
    message: string;
  }> {
    const response = await fetch(`${API_BASE_URL}/chat/create-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify(request),
    });
    return this.handleResponse<{
      success: boolean;
      issue: UserIssueResponse;
      message: string;
    }>(response);
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
  static async analyzeFileDependencies(files: File[], githubToken?: string): Promise<{
    dependencies: FileContextItem[];
    total_tokens: number;
  }> {
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
    return this.handleResponse<{
      dependencies: FileContextItem[];
      total_tokens: number;
    }>(response);
  }

  static async getFileDependencies(fileId: string, githubToken?: string): Promise<FileContextItem[]> {
    const response = await fetch(`${API_BASE_URL}/file-dependencies/${fileId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<FileContextItem[]>(response);
  }

  // Repository Management API Methods
  static async getRepositories(githubToken?: string): Promise<{
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
      headers: this.getAuthHeaders(githubToken),
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

  static async getRepository(owner: string, name: string, githubToken?: string): Promise<{
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
      headers: this.getAuthHeaders(githubToken),
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

  static async createGitHubIssueFromUserIssue(issueId: string, githubToken?: string): Promise<{
    success: boolean;
    github_url: string;
    message: string;
  }> {
    const response = await fetch(`${API_BASE_URL}/issues/${issueId}/create-github-issue`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<{
      success: boolean;
      github_url: string;
      message: string;
    }>(response);
  }

  static async extractFileDependencies(repoUrl: string, githubToken?: string): Promise<{
    children: Array<{
      id: string;
      name: string;
      type: string;
      tokens: number;
      Category: string;
      isDirectory?: boolean;
      children?: Array<{
        id: string;
        name: string;
        type: string;
        tokens: number;
        Category: string;
        isDirectory?: boolean;
        children?: Array<{
          id: string;
          name: string;
          type: string;
          tokens: number;
          Category: string;
          isDirectory?: boolean;
        }>;
      }>;
    }>;
  }> {
    const response = await fetch(`${API_BASE_URL}/filedeps/extract`, {
      method: 'POST',
      headers: this.getAuthHeaders(githubToken),
      body: JSON.stringify({ repo_url: repoUrl }),
    });
    return this.handleResponse<{
      children: Array<{
        id: string;
        name: string;
        type: string;
        tokens: number;
        Category: string;
        isDirectory?: boolean;
        children?: Array<{
          id: string;
          name: string;
          type: string;
          tokens: number;
          Category: string;
          isDirectory?: boolean;
          children?: Array<{
            id: string;
            name: string;
            type: string;
            tokens: number;
            Category: string;
            isDirectory?: boolean;
          }>;
        }>;
      }>;
    }>(response);
  }

  static async getRepositoryBranches(owner: string, repo: string, githubToken?: string): Promise<Array<{
    name: string;
    commit: {
      sha: string;
      url: string;
    };
  }>> {
    const response = await fetch(`${API_BASE_URL}/github/repositories/${owner}/${repo}/branches`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<Array<{
      name: string;
      commit: {
        sha: string;
        url: string;
      };
    }>>(response);
  }

  static async getUserRepositories(githubToken?: string): Promise<Array<{
    id: number;
    name: string;
    full_name: string;
    description: string;
    private: boolean;
    html_url: string;
    default_branch: string;
  }>> {
    const response = await fetch(`${API_BASE_URL}/github/repositories`, {
      method: 'GET',
      headers: this.getAuthHeaders(githubToken),
    });
    return this.handleResponse<Array<{
      id: number;
      name: string;
      full_name: string;
      description: string;
      private: boolean;
      html_url: string;
      default_branch: string;
    }>>(response);
  }
}