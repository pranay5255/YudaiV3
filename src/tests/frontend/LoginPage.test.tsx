import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginPage } from '@/components/LoginPage';

const loginMock = vi.fn();

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    login: loginMock,
    isLoading: false,
    authError: null,
  }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockReset();
  });

  it('renders the full hero headline and preserves auth actions', async () => {
    const user = userEvent.setup();

    render(<LoginPage />);

    expect(
      screen.getByRole('heading', {
        name: /from requirement to issue, tests, and review-ready prs\./i,
      })
    ).toBeVisible();

    expect(screen.getAllByAltText(/yudai labs/i)).toHaveLength(2);

    const installLink = screen.getByRole('link', { name: /install github app/i });
    expect(installLink).toHaveAttribute(
      'href',
      'https://github.com/apps/yudaiv3'
    );

    await user.click(screen.getByRole('button', { name: /sign in with github/i }));
    expect(loginMock).toHaveBeenCalledTimes(1);
  });
});
