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

  // Handle successful authentication by extracting session token from URL
  static handleAuthSuccess(): { sessionToken: string; user: User } | null {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const sessionToken = urlParams.get('session_token');
      const userId = urlParams.get('user_id');
      
      if (sessionToken && userId) {
        // Store session token
        localStorage.setItem('session_token', sessionToken);
        
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
        
        return { sessionToken, user };
      }
      
      return null;
    } catch (error) {
      console.error('Failed to handle auth success:', error);
      return null;
    }
  }

  // Get user by session token (for verification)
  static async getUserBySessionToken(sessionToken: string): Promise<User> {
    const response = await fetch(`${AUTH_BASE_URL}/auth/api/user?session_token=${sessionToken}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get user: ${response.status}`);
    }
    
    const userData = await response.json();
    localStorage.setItem('user_data', JSON.stringify(userData));
    
    return userData;
  }

  // Logout user by deactivating session token
  static async logout(): Promise<void> {
    const sessionToken = this.getStoredSessionToken();
    
    if (sessionToken) {
      try {
        await fetch(`${AUTH_BASE_URL}/auth/api/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ session_token: sessionToken }),
        });
      } catch (error) {
        console.error('Logout API call failed:', error);
        // Continue with local cleanup even if API call fails
      }
    }
    
    // Clear local storage
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_data');
    window.location.href = '/';
  }

  // Check if user is authenticated
  static isAuthenticated(): boolean {
    return !!localStorage.getItem('session_token');
  }

  // Get stored session token
  static getStoredSessionToken(): string | null {
    return localStorage.getItem('session_token');
  }

  // Get stored user data
  static getStoredUserData(): User | null {
    const data = localStorage.getItem('user_data');
    return data ? JSON.parse(data) : null;
  }

  // Verify current authentication
  static async verifyAuth(): Promise<{ authenticated: boolean; user?: User }> {
    const sessionToken = this.getStoredSessionToken();
    const storedUser = this.getStoredUserData();
    
    if (!sessionToken || !storedUser) {
      return { authenticated: false };
    }
    
    try {
      const user = await this.getUserBySessionToken(sessionToken);
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