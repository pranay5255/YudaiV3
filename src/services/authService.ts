import { User, AuthConfig } from '../types';

// Get base URL for auth endpoints - use relative URLs to work with nginx proxy
const getAuthBaseURL = () => {
  // Use localhost:8000 for backend API calls
  return 'https://localhost:8000/';
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

  // GitHub App OAuth login - redirects to GitHub via backend
  static async login(): Promise<void> {
    window.location.href = `${AUTH_BASE_URL}/auth/login`;
  }

  // Handle OAuth success redirect from backend
  static async handleAuthSuccess(): Promise<User> {
    try {
      // Get user profile from backend
      const user = await this.getProfile();
      
      // Store user data
      this.storeUserData(user);
      
      return user;
    } catch (error) {
      console.error('Failed to handle auth success:', error);
      throw error;
    }
  }

  // Handle OAuth error redirect from backend
  static handleAuthError(message?: string): void {
    console.error('Authentication failed:', message);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    window.location.href = '/';
  }

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
} 