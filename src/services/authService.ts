import { User, LoginResponse, AuthConfig } from '../types';

const API_BASE_URL = 'http://localhost:8000';

export class AuthService {
  private static getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('auth_token');
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }

  // GitHub OAuth login - redirects to GitHub
  static async login(): Promise<void> {
    window.location.href = `${API_BASE_URL}/auth/login`;
  }

  // Handle OAuth callback
  static async handleCallback(code: string, state?: string): Promise<LoginResponse> {
    const params = new URLSearchParams({ code });
    if (state) params.append('state', state);
    
    const response = await fetch(`${API_BASE_URL}/auth/callback?${params}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Authentication failed: ${response.status}`);
    }

    const data = await response.json();
    
    // Handle AuthResponse structure from backend
    if (!data.success) {
      throw new Error(data.error || 'Authentication failed');
    }
    
    // Store token in localStorage
    if (data.access_token) {
      localStorage.setItem('auth_token', data.access_token);
    }

    // Return the expected LoginResponse format
    return {
      access_token: data.access_token,
      token_type: 'bearer',
      user: data.user
    };
  }

  // Get current user profile
  static async getProfile(): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/auth/profile`, {
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
      await fetch(`${API_BASE_URL}/auth/logout`, {
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
      const response = await fetch(`${API_BASE_URL}/auth/status`, {
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
    const response = await fetch(`${API_BASE_URL}/auth/config`, {
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
    // Clear URL parameters and let React state handle the redirect
    // The authentication state change will automatically show the main app
    window.history.replaceState({}, document.title, window.location.pathname);
  }
} 