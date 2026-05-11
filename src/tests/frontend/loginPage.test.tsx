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

  it('renders adversarial lifecycle copy with contained primary video and enlarged logo', () => {
    const { container } = render(<LoginPage />);

    expect(screen.getByRole('heading', {
      name: /Yudai Agent Console for adversarial GitHub workflows/i,
    })).toBeInTheDocument();
    expect(screen.getByText('Lifecycle roles')).toBeInTheDocument();
    expect(screen.queryByText('Planning modes')).not.toBeInTheDocument();

    const videos = container.querySelectorAll('video');
    expect(videos).toHaveLength(2);
    expect(videos[1]).toHaveClass('object-contain');
    expect(videos[1]).not.toHaveClass('object-cover');
    expect(videos[1].parentElement).toHaveClass('aspect-video');

    const logo = container.querySelector(`img[src="/assets/baseLogo.png"]`);
    expect(logo).not.toBeNull();
    expect(logo?.parentElement).not.toBeNull();
    expect(logo?.parentElement).toHaveClass('size-12');
    expect(logo).toHaveClass('size-9');
  });
});
