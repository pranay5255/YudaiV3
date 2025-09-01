import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';

/**
 * LoginPage component handles GitHub OAuth login
 * Displays login button and handles any authentication errors
 */
export const LoginPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check for error parameters in URL
  useEffect(() => {
    const errorParam = searchParams.get('error');
    if (errorParam) {
      setError(decodeURIComponent(errorParam));
    }
  }, [searchParams]);

  const handleGitHubLogin = async () => {
    try {
      setIsLoading(true);
      setError(null);

      console.log('[LoginPage] Initiating GitHub OAuth login');

      // Use sessionStore login method
      await useSessionStore.getState().login();

    } catch (error) {
      console.error('[LoginPage] Login failed:', error);
      setError('Failed to initiate login. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-900 flex items-center justify-center">
      <div className="max-w-md w-full mx-auto p-6">
        <div className="bg-zinc-800 rounded-lg shadow-lg p-8 border border-zinc-700">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-fg mb-2">Welcome to Yudai</h1>
            <p className="text-fg/70">Sign in to continue to your AI-powered development workspace</p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-red-500 text-sm">{error}</p>
            </div>
          )}

          {/* Login Button */}
          <button
            onClick={handleGitHubLogin}
            disabled={isLoading}
            className="w-full bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Connecting to GitHub...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clipRule="evenodd" />
                </svg>
                <span>Sign in with GitHub</span>
              </>
            )}
          </button>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-xs text-fg/50">
              By signing in, you agree to our terms of service and privacy policy
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}; 