import { User, LoginResponse, AuthConfig } from '../types';

// Get base URL for auth endpoints (different from API endpoints)
const getAuthBaseURL = () => {
  const apiUrl = import.meta.env.VITE_API_URL || 
    (import.meta.env.DEV ? 'http://localhost:8000' : 'https://yudai.app');
  // For auth endpoints, we need to use the API URL directly (not remove /api)
  return apiUrl;
};

const AUTH_BASE_URL = getAuthBaseURL();

export class AuthService {
  private static getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('auth_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }

  // GitHub App OAuth login - redirects to GitHub
  static async login(): Promise<void> {
    window.location.href = `${AUTH_BASE_URL}/auth/login`;
  }

  // Note: handleCallback method removed - OAuth flow uses redirects, not direct API calls
  // The backend /auth/callback endpoint handles the OAuth redirect and then redirects to frontend
  // Frontend should use handleAuthSuccess() or handleAuthError() to process the redirect

  // Get current user profile
  static async getProfile(): Promise<User> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/profile`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        this.logout();
        throw new Error('Unauthorized');
      }
      throw new Error(`Failed to get profile: ${response.status}`);
    }

    return response.json();
  }

  // Logout user
  static async logout(): Promise<void> {
    try {
      await fetch(`${AUTH_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      });
    } catch (error) {
      console.error('Logout request failed:', error);
    } finally {
      // Always clear local storage
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
    }
  }

  // Check authentication status
  static async checkAuthStatus(): Promise<{ authenticated: boolean; user?: User }> {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return { authenticated: false };
    }

    try {
      const response = await fetch(`${AUTH_BASE_URL}/auth/status`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      if (!response.ok) {
        if (response.status === 401) {
          this.logout();
          return { authenticated: false };
        }
        throw new Error(`Status check failed: ${response.status}`);
      }

      const data = await response.json();
      return {
        authenticated: data.authenticated,
        user: data.user
      };
    } catch (error) {
      console.error('Auth status check failed:', error);
      return { authenticated: false };
    }
  }

  // Get auth configuration
  static async getAuthConfig(): Promise<AuthConfig> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/config`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get auth config: ${response.status}`);
    }

    return response.json();
  }

  // Handle authentication success redirect
  // This is called when user is redirected back from GitHub with success
  static async handleAuthSuccess(): Promise<LoginResponse> {
    const urlParams = new URLSearchParams(window.location.search);
    const userId = urlParams.get('user_id');
    
    if (!userId) {
      throw new Error('No user ID received from authentication success');
    }

    // Check auth status to get user info and token
    const authStatus = await this.checkAuthStatus();
    
    if (!authStatus.authenticated || !authStatus.user) {
      throw new Error('Authentication failed - user not authenticated');
    }

    const token = this.getStoredToken();
    if (!token) {
      throw new Error('No authentication token found');
    }

    return {
      access_token: token,
      token_type: 'bearer',
      user: authStatus.user
    };
  }

  // Handle authentication error redirect
  static handleAuthError(): void {
    const urlParams = new URLSearchParams(window.location.search);
    const errorMessage = urlParams.get('message') || 'Authentication failed';
    
    // Clear any existing auth data
    this.logout();
    
    // You can implement custom error handling here
    console.error('Authentication error:', errorMessage);
    
    // Redirect to login page or show error
    window.location.href = '/login?error=' + encodeURIComponent(errorMessage);
  }

  // Utility methods
  static getStoredToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  static isAuthenticated(): boolean {
    return !!this.getStoredToken();
  }

  static storeUserData(user: User): void {
    localStorage.setItem('user_data', JSON.stringify(user));
  }

  static getStoredUserData(): User | null {
    const userData = localStorage.getItem('user_data');
    return userData ? JSON.parse(userData) : null;
  }

  // Redirect to main application after successful authentication
  static redirectToMainApp(): void {
    // Redirect to the root path which contains the main app with chat interface
    window.location.href = '/';
  }
} 