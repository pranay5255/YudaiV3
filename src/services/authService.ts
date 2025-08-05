import { User, AuthConfig } from '../types';

// Get base URL for auth endpoints - use relative URLs to work with nginx proxy
const getAuthBaseURL = () => {
  // Use relative URLs for auth endpoints to work with nginx proxy
  return '';
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
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to get auth config: ${response.status}`);
    }

    return response.json();
  }

  // Exchange OAuth code for access token
  static async exchangeCodeForToken(code: string, state: string): Promise<{access_token: string}> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/exchange`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code, state }),
    });

    if (!response.ok) {
      throw new Error(`Token exchange failed: ${response.status}`);
    }

    return response.json();
  }

  // Get user info and create/update user
  static async getUserInfoAndCreateUser(accessToken: string): Promise<User> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/user-info`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get user info: ${response.status}`);
    }

    return response.json();
  }

  // Handle auth error
  static handleAuthError(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    window.location.href = '/';
  }

  // Get stored token
  static getStoredToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  // Check if user is authenticated
  static isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  }

  // Store user data
  static storeUserData(user: User): void {
    localStorage.setItem('user_data', JSON.stringify(user));
  }

  // Get stored user data
  static getStoredUserData(): User | null {
    const data = localStorage.getItem('user_data');
    return data ? JSON.parse(data) : null;
  }

  // Redirect to main app
  static redirectToMainApp(): void {
    window.location.href = '/';
  }

  // Validate state parameter
  static async validateState(state: string): Promise<boolean> {
    try {
      const response = await fetch(`${AUTH_BASE_URL}/auth/validate-state`, {
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