import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useSessionStore } from '../stores/sessionStore';

export function AuthSuccess(): JSX.Element {
  const navigate = useNavigate();
  const { clearAuth, setAuthFromCallback } = useAuth();
  const clearSession = useSessionStore((state) => state.clearSession);
  const setActiveTab = useSessionStore((state) => state.setActiveTab);
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) {
      return;
    }

    hasProcessed.current = true;

    const searchParams = new URLSearchParams(window.location.search);
    const sessionToken = searchParams.get('session_token');
    const userId = searchParams.get('user_id');
    const username = searchParams.get('username');
    const name = searchParams.get('name');
    const email = searchParams.get('email');
    const avatar = searchParams.get('avatar');
    const githubId = searchParams.get('github_id');

    if (!sessionToken || !userId || !username) {
      navigate('/auth/login?error=missing_auth_data', { replace: true });
      return;
    }

    clearAuth();
    clearSession();
    setActiveTab('chat');

    setAuthFromCallback({
      sessionToken,
      user: {
        avatar_url: avatar || '',
        created_at: new Date().toISOString(),
        display_name: name || username,
        email: email || '',
        github_user_id: githubId || '',
        github_username: username,
        id: Number.parseInt(userId, 10),
        last_login: new Date().toISOString(),
      },
    });

    navigate('/', { replace: true });
  }, [clearAuth, clearSession, navigate, setActiveTab, setAuthFromCallback]);

  return (
    <main className="grid min-h-dvh place-items-center bg-bg text-fg">
      <section className="rounded-lg bg-bg-secondary p-5 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
        <div className="relative mx-auto mb-4 grid size-12 place-items-center rounded-lg bg-emerald-500/10 text-emerald-200 shadow-[0_0_0_1px_rgba(16,185,129,0.22)]">
          <Loader2 aria-hidden="true" className="absolute size-8 animate-spin opacity-45" />
          <CheckCircle2 aria-hidden="true" className="size-5" />
        </div>
        <p className="text-sm font-medium">Completing authentication</p>
        <p className="mt-1 text-xs text-fg-muted">GitHub session</p>
      </section>
    </main>
  );
}
