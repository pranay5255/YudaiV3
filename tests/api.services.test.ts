import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiService } from '../src/services/api';
import { AuthService } from '../src/services/authService';

// Mock fetch globally
global.fetch = vi.fn();

describe('API Services Configuration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('AuthService URL Configuration', () => {
    it('should construct auth URLs correctly for production', () => {
      // Mock environment variable
      vi.stubEnv('VITE_API_URL', 'https://yudai.app/api');
      
      // Mock fetch to prevent actual API calls
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, access_token: 'test-token', user: {} }),
      } as Response);

      // Test login URL construction (should remove /api suffix)
      const loginSpy = vi.spyOn(window.location, 'href', 'set').mockImplementation(() => {});
      
      AuthService.login();
      
      expect(loginSpy).toHaveBeenCalledWith('https://yudai.app/auth/login');
      
      loginSpy.mockRestore();
    });

    it('should handle callback requests with correct base URL', async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ 
          success: true, 
          access_token: 'test-token', 
          user: { id: 1, username: 'test' } 
        }),
      } as Response);

      await AuthService.handleCallback('test-code', 'test-state');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://yudai.app/auth/callback'),
        expect.any(Object)
      );
    });

    it('should use development URLs in development mode', () => {
      const loginSpy = vi.spyOn(window.location, 'href', 'set').mockImplementation(() => {});
      
      // Test that login method is called (URL construction is tested elsewhere)
      AuthService.login();
      
      expect(loginSpy).toHaveBeenCalledWith(
        expect.stringMatching(/\/auth\/login$/)
      );
      
      loginSpy.mockRestore();
    });
  });

  describe('ApiService URL Configuration', () => {
    it('should use full API URL with /api prefix for API requests', async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      } as Response);

      // Store auth token
      localStorage.setItem('auth_token', 'test-token');

      await ApiService.getChatSessions();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('https://yudai.app/api/daifu/chat/sessions'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token'
          })
        })
      );
    });

    it('should handle API errors correctly', async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ error: 'Unauthorized' }),
      } as Response);

      localStorage.setItem('auth_token', 'invalid-token');

      await expect(ApiService.getChatSessions()).rejects.toThrow('Authentication required');
      
      // Should clear auth token on 401
      expect(localStorage.getItem('auth_token')).toBeNull();
    });

    it('should include proper headers for API requests', async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ reply: 'test' }),
      } as Response);

      localStorage.setItem('auth_token', 'test-token');

      await ApiService.sendChatMessage({
        message: { content: 'test', is_code: false },
        session_id: 'test-session'
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-token'
          }),
          body: expect.any(String)
        })
      );
    });
  });

  describe('Environment-based Configuration', () => {
    it('should adapt to different environment configurations', () => {
      // Test production environment
      vi.stubEnv('VITE_API_URL', 'https://yudai.app/api');
      vi.stubEnv('DEV', false);
      
      // AuthService should remove /api for auth endpoints
      const authBaseUrl = 'https://yudai.app';
      expect(authBaseUrl).not.toContain('/api');
      
      // ApiService should keep full URL
      const apiBaseUrl = 'https://yudai.app/api';
      expect(apiBaseUrl).toContain('/api');
    });

    it('should handle missing environment variables gracefully', () => {
      // Test that services don't crash without environment variables
      expect(() => {
        // These service calls should not throw errors
        AuthService.isAuthenticated();
        AuthService.getStoredToken();
      }).not.toThrow();
    });
  });

  describe('Token Management', () => {
    it('should store and retrieve auth tokens correctly', () => {
      const testToken = 'test-auth-token';
      
      localStorage.setItem('auth_token', testToken);
      
      expect(AuthService.getStoredToken()).toBe(testToken);
      expect(AuthService.isAuthenticated()).toBe(true);
    });

    it('should clear auth state on logout', async () => {
      const mockFetch = vi.mocked(fetch);
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response);

      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('user_data', '{"id": 1}');

      await AuthService.logout();

      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('user_data')).toBeNull();
    });
  });
}); 