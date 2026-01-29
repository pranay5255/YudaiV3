import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { logger } from '../utils/logger';

/**
 * AuthCallback component handles OAuth error callbacks from the backend
 * Redirects to login page with proper error messages
 */
export const AuthCallback: React.FC = () => {
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
      logger.error('[Auth] OAuth error received:', error);
      // Redirect to login page with the error
      navigate(`/auth/login?error=${encodeURIComponent(error)}`, { replace: true });
    } else {
      // No error, redirect to login
      navigate('/auth/login', { replace: true });
    }
  }, [navigate]);

  return (
    <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-500 mx-auto mb-4"></div>
        <p className="text-fg/70">Processing authentication...</p>
        <p className="text-xs text-fg/50 mt-2">Redirecting to login...</p>
      </div>
    </div>
  );
};
