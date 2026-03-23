import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '@/stores/authStore';

const resetStore = () => {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    sessionToken: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });
};

describe('authStore.initializeAuth', () => {
  beforeEach(() => {
    resetStore();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetStore();
  });

  it('does not call /auth/api/user when no session token exists', async () => {
    await useAuthStore.getState().initializeAuth();

    expect(fetch).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });
});
