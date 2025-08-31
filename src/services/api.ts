// DEPRECATED: This service is being phased out in favor of unified sessionStore + useSessionQueries
// All operations should now go through the session context via Zustand store
// This file will be removed once all components migrate to the unified state management
//
// Migration Guide:
// - Auth operations: Use useAuth() hook from sessionStore
// - Chat operations: Use useChatMessages() and related hooks
// - Session operations: Use useSession() and session management hooks
// - Repository operations: Use useRepository() hook
// - All other operations: Use appropriate hooks from useSessionQueries.ts

// UserIssue import removed - no longer used in this deprecated file
import type {
  ChatRequest,
  ChatResponse,
  CreateIssueWithContextRequest,
  IssueCreationResponse,
  GitHubRepository,
  GitHubBranch,
  ExtractFileDependenciesRequest,
  ExtractFileDependenciesResponse,
} from '../types/sessionTypes';

// Keep legacy types for backward compatibility
import type {
  ValidateSessionResponse,
  LogoutRequest,
  LogoutResponse,
  LoginUrlResponse,
  CreateGitHubIssueResponse,
  RepositoryResponse,
} from '../types/api';

// Import centralized API configuration
import { API_CONFIG, buildApiUrl, API_REQUEST_CONFIG } from '../config/api';

export class ApiService {
  private static getAuthHeaders(sessionToken?: string): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    // Use token from parameter or localStorage
    const token = sessionToken || localStorage.getItem('session_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    return headers;
  }

  private static async handleResponse<T>(response: Response): Promise<T> {
    console.log('[ApiService] handleResponse called with status:', response.status);
    
    if (!response.ok) {
      console.error('[ApiService] Response not ok, status:', response.status);
      
      if (response.status === 401) {
        console.log('[ApiService] 401 Unauthorized, redirecting to login');
        // Redirect to login instead of clearing localStorage
        window.location.href = '/auth/login';
        throw new Error('Authentication required');
      }
      
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.message || errorMessage;
        console.error('[ApiService] Parsed error data:', errorData);
      } catch (parseError) {
        console.error('[ApiService] Failed to parse error JSON:', parseError);
        // If we can't parse error JSON, use the default message
      }
      
      console.error('[ApiService] Throwing error:', errorMessage);
      throw new Error(errorMessage);
    }

    console.log('[ApiService] Response ok, parsing JSON');
    try {
      const data = await response.json();
      console.log('[ApiService] Successfully parsed response:', data);
      return data;
    } catch (parseError) {
      console.error('[ApiService] Failed to parse response JSON:', parseError);
      throw new Error('Failed to parse response');
    }
  }

  // DEPRECATED: Use useAuth() hook from sessionStore instead
  // Authentication API Methods (backend/auth/auth_routes.py)
  static async validateSessionToken(sessionToken: string): Promise<ValidateSessionResponse> {
    console.warn('[ApiService] DEPRECATED: validateSessionToken should be replaced with useAuth() hook');
    console.log('[ApiService] Validating session token:', sessionToken ? 'Token provided' : 'No token');
    const url = buildApiUrl(API_CONFIG.AUTH.USER);
    console.log('[ApiService] Making request to:', url);

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          ...API_REQUEST_CONFIG.DEFAULT_HEADERS,
          'Authorization': `Bearer ${sessionToken}`,
        },
      });

      console.log('[ApiService] Response status:', response.status);
      console.log('[ApiService] Response ok:', response.ok);

      if (!response.ok) {
        console.error('[ApiService] Validation failed with status:', response.status);
        const errorText = await response.text();
        console.error('[ApiService] Error response body:', errorText);
      }

      return ApiService.handleResponse<ValidateSessionResponse>(response);
    } catch (error) {
      console.error('[ApiService] Exception during session validation:', error);
      throw error;
    }
  }

  static async logout(sessionToken: string): Promise<LogoutResponse> {
    const url = buildApiUrl(API_CONFIG.AUTH.LOGOUT);
    const response = await fetch(url, {
      method: 'POST',
      headers: API_REQUEST_CONFIG.DEFAULT_HEADERS,
      body: JSON.stringify({ session_token: sessionToken } as LogoutRequest),
    });
    return ApiService.handleResponse<LogoutResponse>(response);
  }

  static async getLoginUrl(): Promise<LoginUrlResponse> {
    const url = buildApiUrl(API_CONFIG.AUTH.LOGIN);
    const response = await fetch(url, {
      method: 'GET',
      headers: API_REQUEST_CONFIG.DEFAULT_HEADERS,
    });
    return ApiService.handleResponse<LoginUrlResponse>(response);
  }

  // DEPRECATED: Use useChatMessages() hook and related mutations from useSessionQueries instead
  // Chat API Methods (backend/daifuUserAgent/chat_api.py)
  static async sendChatMessage(request: ChatRequest, sessionToken?: string): Promise<ChatResponse> {
    console.warn('[ApiService] DEPRECATED: sendChatMessage should be replaced with useChatMessages() hook');
    // Validate session_id is required
    if (!request.session_id?.trim()) {
      throw new Error('session_id is required and cannot be empty');
    }

    const url = buildApiUrl(API_CONFIG.DAIFU.CHAT);
    const response = await fetch(url, {
      method: 'POST',
      headers: ApiService.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return ApiService.handleResponse<ChatResponse>(response);
  }



  // Issue Management API Methods (backend/issueChatServices/issue_service.py)
  static async createIssueWithContext(request: CreateIssueWithContextRequest, sessionToken?: string): Promise<IssueCreationResponse> {
    const url = buildApiUrl(API_CONFIG.ISSUES.CREATE_WITH_CONTEXT);
    const response = await fetch(url, {
      method: 'POST',
      headers: ApiService.getAuthHeaders(sessionToken),
      body: JSON.stringify(request),
    });
    return ApiService.handleResponse<IssueCreationResponse>(response);
  }


  






  // File Dependencies API Methods (backend/repo_processorGitIngest/filedeps.py)




  // DEPRECATED: Use useRepository() hook from sessionStore instead
  // Repository Management API Methods (backend/github/github_routes.py)
  static async getRepositories(sessionToken?: string): Promise<RepositoryResponse> {
    console.warn('[ApiService] DEPRECATED: getRepositories should be replaced with useRepository() hook');
    // Note: This endpoint might need to be clarified - could be GitHub repos or general repos
    const url = buildApiUrl(API_CONFIG.GITHUB.REPOS);
    const response = await fetch(url, {
      method: 'GET',
      headers: ApiService.getAuthHeaders(sessionToken),
    });
    return ApiService.handleResponse<RepositoryResponse>(response);
  }



  static async createGitHubIssueFromUserIssue(issueId: string, sessionToken?: string): Promise<CreateGitHubIssueResponse> {
    const url = buildApiUrl(API_CONFIG.ISSUES.CREATE_GITHUB_ISSUE, { issueId });
    const response = await fetch(url, {
      method: 'POST',
      headers: ApiService.getAuthHeaders(sessionToken),
    });
    return ApiService.handleResponse<CreateGitHubIssueResponse>(response);
  }

  static async extractFileDependencies(repoUrl: string, sessionToken?: string): Promise<ExtractFileDependenciesResponse> {
    const url = buildApiUrl(API_CONFIG.FILEDEPS.EXTRACT);
    const response = await fetch(url, {
      method: 'POST',
      headers: ApiService.getAuthHeaders(sessionToken),
      body: JSON.stringify({ repo_url: repoUrl } as ExtractFileDependenciesRequest),
    });
    return ApiService.handleResponse<ExtractFileDependenciesResponse>(response);
  }

  static async getRepositoryBranches(owner: string, repo: string, sessionToken?: string): Promise<GitHubBranch[]> {
    const url = buildApiUrl(API_CONFIG.GITHUB.REPO_BRANCHES, { owner, repo });
    const response = await fetch(url, {
      method: 'GET',
      headers: ApiService.getAuthHeaders(sessionToken),
    });
    return ApiService.handleResponse<GitHubBranch[]>(response);
  }

  static async getUserRepositories(sessionToken?: string): Promise<GitHubRepository[]> {
    const url = buildApiUrl(API_CONFIG.GITHUB.USER_REPOS);
    const response = await fetch(url, {
      method: 'GET',
      headers: ApiService.getAuthHeaders(sessionToken),
    });
    return ApiService.handleResponse<GitHubRepository[]>(response);
  }
}