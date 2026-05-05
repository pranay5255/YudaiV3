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

  it('validates an existing session token through the auth REST API', async () => {
    useAuthStore.setState({
      sessionToken: 'session-token',
      isAuthenticated: false,
    });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({
      avatar_url: 'https://example.com/avatar.png',
      display_name: 'Test User',
      email: 'tester@example.com',
      github_id: '123',
      github_username: 'tester',
      id: '42',
    }), {
      headers: { 'content-type': 'application/json' },
      status: 200,
    }));

    await useAuthStore.getState().initializeAuth();

    expect(fetch).toHaveBeenCalledWith('/api/auth/api/user', {
      method: 'GET',
      headers: {
        Authorization: 'Bearer session-token',
        'Content-Type': 'application/json',
      },
    });
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.github_username).toBe('tester');
  });

  it('requests the GitHub login URL from the auth REST API', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({
      login_url: 'https://github.com/login/oauth/authorize?client_id=test',
    }), {
      headers: { 'content-type': 'application/json' },
      status: 200,
    }));
    const originalLocation = window.location;
    const locationStub = { ...originalLocation, href: '' } as Location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: locationStub,
    });

    await useAuthStore.getState().login();

    expect(fetch).toHaveBeenCalledWith('/api/auth/api/login', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    expect(window.location.href).toBe(
      'https://github.com/login/oauth/authorize?client_id=test'
    );

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });
});
