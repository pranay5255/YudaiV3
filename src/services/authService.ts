import { User } from '../types/unifiedState';

// Get base URL for auth endpoints
const getAuthBaseURL = () => {
  return 'https://api.yudai.app';
};

const AUTH_BASE_URL = getAuthBaseURL();

export class AuthService {
  // Simple GitHub OAuth login - matches Ruby approach
  static async login(): Promise<void> {
    try {
      // Get login URL from backend
      const response = await fetch(`${AUTH_BASE_URL}/auth/api/login`);
      const data = await response.json();
      
      if (data.login_url) {
        // Redirect to GitHub OAuth - simple like Ruby
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
        
        // Create user object from URL params (simplified)
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
    
    // Store user data
    localStorage.setItem('user_data', JSON.stringify(userData));
    
    return userData;
  }

  // Simple logout - just clear local storage
  static logout(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    
    // Redirect to home
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
    
    if (!token) {
      return { authenticated: false };
    }
    
    try {
      const user = await this.getUserByToken(token);
      return { authenticated: true, user };
    } catch (error) {
      console.error('Auth verification failed:', error);
      // Clear invalid token
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
    window.location.href = '/';
  }
}