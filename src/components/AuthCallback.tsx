import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Loader2 } from 'lucide-react';

export function AuthCallback(): JSX.Element {
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) {
      return;
    }

    hasProcessed.current = true;

    const searchParams = new URLSearchParams(window.location.search);
    const error = searchParams.get('error');

    if (error) {
      navigate(`/auth/login?error=${encodeURIComponent(error)}`, { replace: true });
      return;
    }

    navigate('/auth/login', { replace: true });
  }, [navigate]);

  return (
    <main className="grid min-h-dvh place-items-center bg-bg text-fg">
      <section className="rounded-lg bg-bg-secondary p-5 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
        <div className="relative mx-auto mb-4 grid size-12 place-items-center rounded-lg bg-red-500/10 text-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.24)]">
          <Loader2 aria-hidden="true" className="absolute size-8 animate-spin opacity-45" />
          <AlertCircle aria-hidden="true" className="size-5" />
        </div>
        <p className="text-sm font-medium">Processing authentication</p>
        <p className="mt-1 text-xs text-fg-muted">GitHub callback</p>
      </section>
    </main>
  );
}
