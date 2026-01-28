import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

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

  // Show loading spinner while checking authentication (with timeout fallback)
  if (isLoading) {
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

  // Redirect to login if not authenticated
  if (!isAuthenticated || !user) {
    return fallback ? <>{fallback}</> : <Navigate to="/auth/login" replace />;
  }

  // Render protected content
  return <>{children}</>;
};
