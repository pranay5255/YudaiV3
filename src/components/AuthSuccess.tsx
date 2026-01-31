import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useSessionStore } from '../stores/sessionStore';
import { useQueryClient } from '@tanstack/react-query';

/**
 * AuthSuccess component handles the OAuth callback from GitHub
 * Processes URL parameters and sets up the user session
 */
export const AuthSuccess: React.FC = () => {
  const navigate = useNavigate();
  const { setAuthFromCallback, clearAuth } = useAuth();
  const clearSession = useSessionStore((state) => state.clearSession);
  const queryClient = useQueryClient();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) {
      return;
    }

    hasProcessed.current = true;

    const handleAuthSuccess = async () => {
      try {
        console.log('[AuthSuccess] Processing OAuth callback data');

        const searchParams = new URLSearchParams(window.location.search);

        // Extract auth data from URL parameters
        const sessionToken = searchParams.get('session_token');
        const userId = searchParams.get('user_id');
        const username = searchParams.get('username');
        const name = searchParams.get('name');
        const email = searchParams.get('email');
        const avatar = searchParams.get('avatar');
        const githubId = searchParams.get('github_id');

        if (!sessionToken || !userId || !username) {
          console.error('[AuthSuccess] Missing required auth parameters');
          navigate('/auth/login?error=missing_auth_data');
          return;
        }

        // Create user object from callback data
        const user = {
          id: parseInt(userId),
          github_username: username,
          github_user_id: githubId || '',
          email: email || '',
          display_name: name || username,
          avatar_url: avatar || '',
          created_at: new Date().toISOString(),
          last_login: new Date().toISOString(),
        };

        console.log('[AuthSuccess] Setting up user session:', user);

        // Ensure any prior auth/session data is cleared before applying the new token.
        clearAuth();
        clearSession();
        queryClient.clear();

        // Set up the session using the session store
        setAuthFromCallback({
          user,
          sessionToken,
        });

        console.log('[AuthSuccess] Authentication successful, redirecting to main app');
        
        // Redirect to the main application
        navigate('/', { replace: true });

      } catch (error) {
        console.error('[AuthSuccess] Error processing auth callback:', error);
        navigate('/auth/login?error=auth_processing_failed');
      }
    };

    handleAuthSuccess();
  }, [navigate, setAuthFromCallback, clearSession]);

  return (
    <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-fg/70">Completing authentication...</p>
        <p className="text-xs text-fg/50 mt-2">Please wait while we set up your session...</p>
      </div>
    </div>
  );
};
