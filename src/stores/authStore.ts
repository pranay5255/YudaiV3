import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { User } from '../types/sessionTypes';
import { API, buildApiUrl } from '../config/api';

interface AuthState {
  user: User | null;
  sessionToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  initializeAuth: () => Promise<void>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  setAuthFromCallback: (authData: { user: User; sessionToken: string }) => void;
  clearAuth: () => void;
}

const getAuthHeaders = (sessionToken?: string): HeadersInit => {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (sessionToken) {
    headers['Authorization'] = `Bearer ${sessionToken}`;
  }
  return headers;
};

export const useAuthStore = create<AuthState>()(
  devtools(
    (set, get) => ({
      user: null,
      sessionToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      initializeAuth: async () => {
        const existingToken = get().sessionToken;

        set({ isLoading: true, error: null });

        try {
          const response = await fetch(buildApiUrl(API.AUTH.USER), {
            method: 'GET',
            headers: getAuthHeaders(existingToken || undefined),
          });

          if (!response.ok) {
            set({
              user: null,
              sessionToken: existingToken,
              isAuthenticated: false,
              isLoading: false,
              error: null,
            });
            return;
          }

          const userData = await response.json() as {
            id: string;
            github_username: string;
            github_id: string;
            email: string;
            display_name: string;
            avatar_url: string;
          };

          const user: User = {
            id: parseInt(userData.id),
            github_username: userData.github_username,
            github_user_id: userData.github_id,
            email: userData.email,
            display_name: userData.display_name,
            avatar_url: userData.avatar_url,
            created_at: new Date().toISOString(),
            last_login: new Date().toISOString(),
          };

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          console.error('[AuthStore] Auth initialization failed:', error);
          set({
            user: null,
            sessionToken: existingToken,
            isAuthenticated: false,
            isLoading: false,
            error: 'Auth initialization failed',
          });
        }
      },

      login: async () => {
        try {
          set({ isLoading: true, error: null });

          const response = await fetch(buildApiUrl(API.AUTH.LOGIN), {
            method: 'GET',
            headers: getAuthHeaders(),
          });

          if (!response.ok) {
            throw new Error(`Login failed: ${response.status}`);
          }

          const { login_url } = await response.json() as { login_url: string };
          window.location.href = login_url;
        } catch (error) {
          console.error('[AuthStore] Login failed:', error);
          set({ isLoading: false, error: 'Login failed' });
          throw error;
        }
      },

      logout: async () => {
        const sessionToken = get().sessionToken;

        try {
          if (sessionToken) {
            await fetch(buildApiUrl(API.AUTH.LOGOUT), {
              method: 'POST',
              headers: getAuthHeaders(sessionToken),
              body: JSON.stringify({ session_token: sessionToken }),
            });
          }
        } catch (error) {
          console.warn('[AuthStore] Logout API call failed:', error);
        } finally {
          set({
            user: null,
            sessionToken: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          });
          window.location.href = '/auth/login';
        }
      },

      refreshAuth: async () => {
        await get().initializeAuth();
      },

      setAuthFromCallback: (authData: { user: User; sessionToken: string }) => {
        set({
          user: authData.user,
          sessionToken: authData.sessionToken,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
      },

      clearAuth: () => {
        set({
          user: null,
          sessionToken: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      },
    }),
    { name: 'auth-store' }
  )
);
