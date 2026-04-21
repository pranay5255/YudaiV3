import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

interface ProtectedRouteProps {
  children: ReactNode;
  fallback?: ReactNode;
  loadingComponent?: ReactNode;
}

export function ProtectedRoute({
  children,
  fallback,
  loadingComponent,
}: ProtectedRouteProps): JSX.Element {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return loadingComponent ? (
      <>{loadingComponent}</>
    ) : (
      <div className="grid min-h-dvh place-items-center bg-bg text-fg">
        <div className="rounded-lg bg-bg-secondary p-5 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
          <div className="mx-auto mb-4 grid size-12 place-items-center rounded-lg bg-cyan/10 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.2)]">
            <Loader2 aria-hidden="true" className="size-5 animate-spin" />
          </div>
          <p className="text-sm font-medium">Verifying session</p>
          <p className="mt-1 text-xs text-fg-muted">GitHub authentication</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return fallback ? <>{fallback}</> : <Navigate replace to="/auth/login" />;
  }

  return <div className="min-h-dvh">{children}</div>;
}
