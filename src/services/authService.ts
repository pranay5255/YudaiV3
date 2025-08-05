import { User } from '../types/unifiedState';

const AUTH_BASE_URL = 'https://api.yudai.app';

export class AuthService {
  // Simple GitHub OAuth login
  static async login(): Promise<void> {
    try {
      const response = await fetch(`${AUTH_BASE_URL}/auth/api/login`);
      const data = await response.json();
      
      if (data.login_url) {
        window.location.href = data.login_url;
      } else {
        throw new Error('Failed to get login URL');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  // Handle successful authentication by extracting token from URL
  static handleAuthSuccess(): { token: string; user: User } | null {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get('token');
      const userId = urlParams.get('user_id');
      
      if (token && userId) {
        // Store token
        localStorage.setItem('auth_token', token);
        
        // Create user object from URL params
        const user: User = {
          id: parseInt(userId),
          github_username: urlParams.get('username') || '',
          display_name: urlParams.get('name') || '',
          email: urlParams.get('email') || '',
          avatar_url: urlParams.get('avatar') || '',
          github_id: urlParams.get('github_id') || '',
        };
        
        localStorage.setItem('user_data', JSON.stringify(user));
        
        return { token, user };
      }
      
      return null;
    } catch (error) {
      console.error('Failed to handle auth success:', error);
      return null;
    }
  }

  // Get user by token (for verification)
  static async getUserByToken(token: string): Promise<User> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/api/user?token=${token}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get user: ${response.status}`);
    }
    
    const userData = await response.json();
    localStorage.setItem('user_data', JSON.stringify(userData));
    
    return userData;
  }

  // Simple logout
  static logout(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    window.location.href = '/';
  }

  // Check if user is authenticated
  static isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  }

  // Get stored token
  static getStoredToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  // Get stored user data
  static getStoredUserData(): User | null {
    const data = localStorage.getItem('user_data');
    return data ? JSON.parse(data) : null;
  }

  // Verify current authentication
  static async verifyAuth(): Promise<{ authenticated: boolean; user?: User }> {
    const token = this.getStoredToken();
    const storedUser = this.getStoredUserData();
    
    if (!token || !storedUser) {
      return { authenticated: false };
    }
    
    try {
      const user = await this.getUserByToken(token);
      return { authenticated: true, user };
    } catch (error) {
      console.error('Auth verification failed:', error);
      this.logout();
      return { authenticated: false };
    }
  }

  // Handle authentication error
  static handleAuthError(message?: string): void {
    console.error('Authentication failed:', message);
    this.logout();
  }

  // Redirect to main app
  static redirectToMainApp(): void {
    window.location.replace(window.location.origin + '/');
  }
}