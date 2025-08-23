import React, { ReactNode, useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { LoginPage } from '../components/LoginPage';

interface ProtectedRouteProps {
  children: ReactNode;
  fallback?: ReactNode;
  loadingComponent?: ReactNode;
}

/**
 * ProtectedRoute component that guards routes requiring authentication
 * Shows loading spinner during auth verification
 * Redirects to login if not authenticated
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  fallback,
  loadingComponent
}) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const [timeoutReached, setTimeoutReached] = useState(false);

  // Add timeout to prevent infinite loading
  useEffect(() => {
    const timer = setTimeout(() => {
      console.warn('[ProtectedRoute] Authentication timeout reached, forcing login page');
      setTimeoutReached(true);
    }, 5000); // 5 second timeout

    return () => clearTimeout(timer);
  }, []);

  // Show loading spinner while checking authentication (with timeout fallback)
  if (isLoading && !timeoutReached) {
    return loadingComponent || (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-fg/70">Verifying authentication...</p>
          <p className="text-xs text-fg/50 mt-2">This may take a few seconds...</p>
        </div>
      </div>
    );
  }

  // Show login page if not authenticated or timeout reached
  if (!isAuthenticated || !user || timeoutReached) {
    return fallback ? <>{fallback}</> : <LoginPage />;
  }

  // Render protected content
  return <>{children}</>;
};