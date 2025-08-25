import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

/**
 * AuthCallback component handles OAuth error callbacks from the backend
 * Redirects to login page with proper error messages
 */
export const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const error = searchParams.get('error');
    if (error) {
      console.error('[AuthCallback] OAuth error received:', error);
      // Redirect to login page with the error
      navigate(`/auth/login?error=${encodeURIComponent(error)}`, { replace: true });
    } else {
      // No error, redirect to login
      navigate('/auth/login', { replace: true });
    }
  }, [searchParams, navigate]);

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
