import React, { useEffect, useState } from 'react';
import { AuthService } from '../services/authService';
import { useAuth } from '../hooks/useAuth';

interface AuthCallbackProps {
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export const AuthCallback: React.FC<AuthCallbackProps> = ({ onSuccess, onError }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { refreshAuth } = useAuth();

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        setIsLoading(true);
        
        // Check if this is a success or error redirect
        const urlParams = new URLSearchParams(window.location.search);
        const errorMessage = urlParams.get('message');
        
        if (errorMessage) {
          // This is an error redirect
          setError(errorMessage);
          AuthService.handleAuthError();
          onError?.(errorMessage);
          return;
        }
        
        // This is a success redirect
        const loginResponse = await AuthService.handleAuthSuccess();
        
        // Store user data
        AuthService.storeUserData(loginResponse.user);
        
        // Refresh auth state in the context
        await refreshAuth();
        
        // Call the success callback
        onSuccess?.();
        
        // Redirect to main app
        AuthService.redirectToMainApp();
        
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Authentication failed';
        setError(errorMessage);
        onError?.(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    handleAuthCallback();
  }, [onSuccess, onError, refreshAuth]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-fg mb-2">Completing Authentication</h2>
          <p className="text-fg/70">Please wait while we complete your GitHub App authentication...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-fg mb-2">Authentication Failed</h2>
          <p className="text-fg/70 mb-6">{error}</p>
          <button
            onClick={() => AuthService.login()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return null;
}; 