import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '@/components/LoginPage';

const loginMock = vi.fn<() => Promise<void>>();

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    authError: null,
    isLoading: false,
    login: loginMock,
  }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockResolvedValue(undefined);
    window.history.pushState({}, '', '/auth/login');
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('starts GitHub REST auth when the user clicks continue', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole('button', { name: /continue with github/i }));

    expect(loginMock).toHaveBeenCalledTimes(1);
  });

  it('keeps a login failure visible on the landing page', async () => {
    loginMock.mockRejectedValueOnce(new Error('Login exploded'));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole('button', { name: /continue with github/i }));

    expect(await screen.findByText('Login exploded')).toBeInTheDocument();
  });

  it('renders route auth errors from the OAuth callback', async () => {
    window.history.pushState({}, '', '/auth/login?error=missing_auth_data');

    render(<LoginPage />);

    await waitFor(() => {
      expect(screen.getByText('missing auth data')).toBeInTheDocument();
    });
  });
});
