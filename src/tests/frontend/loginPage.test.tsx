import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '@/components/LoginPage';

const authMock = vi.hoisted(() => ({
  login: vi.fn<() => Promise<void>>(),
  state: {
    authError: null as string | null,
    isLoading: false,
  },
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    authError: authMock.state.authError,
    isLoading: authMock.state.isLoading,
    login: authMock.login,
  }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    authMock.login.mockResolvedValue(undefined);
    authMock.state.authError = null;
    authMock.state.isLoading = false;
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

    expect(authMock.login).toHaveBeenCalledTimes(1);
  });

  it('shows the loading state on GitHub CTAs', () => {
    authMock.state.isLoading = true;
    render(<LoginPage />);

    const loadingButtons = screen.getAllByRole('button', { name: /opening github/i });
    expect(loadingButtons.length).toBeGreaterThanOrEqual(1);
    expect(loadingButtons[0]).toBeDisabled();
  });

  it('keeps a login failure visible on the landing page', async () => {
    authMock.login.mockRejectedValueOnce(new Error('Login exploded'));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.click(screen.getByRole('button', { name: /continue with github/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Login exploded');
  });

  it('renders route auth errors from the OAuth callback', async () => {
    window.history.pushState({}, '', '/auth/login?error=missing_auth_data');

    render(<LoginPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('missing auth data');
    });
  });

  it('renders auth store errors visibly', () => {
    authMock.state.authError = 'GitHub unavailable';

    render(<LoginPage />);

    expect(screen.getByRole('alert')).toHaveTextContent('GitHub unavailable');
  });

  it('renders the new landing structure, anchors, logo, and product video', () => {
    const { container } = render(<LoginPage />);

    expect(screen.getByRole('heading', { level: 1, name: /Yudai Labs/i })).toBeInTheDocument();

    const primaryNav = screen.getByRole('navigation', { name: /primary/i });
    for (const label of ['Product', 'Workflow', 'Security', 'Docs', 'Get Started']) {
      const link = within(primaryNav).getByRole('link', { name: label });
      expect(link).toHaveAttribute('href', `#${label.toLowerCase().replace(' ', '-')}`);
    }

    const logo = screen.getByAltText('Yudai Labs logo');
    expect(logo).toHaveAttribute('src', '/assets/baseLogo.png');
    expect(logo).toHaveClass('yudai-hero-logo__mark');

    const video = container.querySelector('video[src="/videos/yudai-enterprise-intro.mp4"]');
    expect(video).not.toBeNull();
    expect(video).toHaveClass('yudai-workflow-video');
    expect(video).toHaveAttribute('controls');
    expect(video).not.toHaveAttribute('aria-hidden');
  });
});
