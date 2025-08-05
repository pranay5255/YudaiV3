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
  const [isSuccess, setIsSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string>('');
  const { refreshAuth } = useAuth();

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        setIsLoading(true);
        
        const urlParams = new URLSearchParams(window.location.search);
        const errorMessage = urlParams.get('error');
        
        if (errorMessage) {
          // Handle error case
          setError(errorMessage);
          AuthService.handleAuthError(errorMessage);
          onError?.(errorMessage);
          return;
        }
        
        // Try to handle successful authentication from URL params
        const authResult = AuthService.handleAuthSuccess();
        
        if (authResult) {
          // Success - we have token and user data from URL params
          try {
            // Refresh auth state in the context
            if (refreshAuth) {
              await refreshAuth();
            }
            
            // Call success callback
            onSuccess?.();
            
            // Show success state
            const displayName = authResult.user.display_name || authResult.user.github_username;
            setSuccessMessage(`Successfully authorized! Welcome, ${displayName} (${authResult.user.github_username}).`);
            setIsSuccess(true);
            
            // Redirect to main app after showing success
            setTimeout(() => {
              AuthService.redirectToMainApp();
            }, 2000);
          } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Authentication processing failed';
            setError(errorMsg);
            AuthService.handleAuthError(errorMsg);
            onError?.(errorMsg);
          }
        } else {
          // No auth data found
          throw new Error('No authentication data found');
        }
        
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Authentication failed';
        setError(errorMessage);
        AuthService.handleAuthError(errorMessage);
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
          <p className="text-fg/70">Please wait while we complete your GitHub authentication...</p>
        </div>
      </div>
    );
  }

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-green-500 text-6xl mb-4">✅</div>
          <h2 className="text-xl font-semibold text-fg mb-2">Authentication Successful</h2>
          <p className="text-fg/70 mb-6">{successMessage}</p>
          <div className="animate-pulse text-blue-500">Redirecting to main app...</div>
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