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
        
        console.log('AuthCallback: Starting auth callback handling');
        console.log('AuthCallback: Current URL:', window.location.href);
        
        // Check if this is an error redirect from backend
        const urlParams = new URLSearchParams(window.location.search);
        const errorMessage = urlParams.get('error') || urlParams.get('message');
        
        console.log('AuthCallback: URL params:', Object.fromEntries(urlParams.entries()));
        
        if (errorMessage) {
          // Handle error case
          console.log('AuthCallback: Error detected:', errorMessage);
          setError(errorMessage);
          AuthService.handleAuthError(errorMessage);
          onError?.(errorMessage);
          return;
        }
        
        // Try to handle successful authentication
        const authResult = AuthService.handleAuthSuccess();
        
        console.log('AuthCallback: Auth result:', authResult);
        
        if (authResult) {
          // Success - we have token and user data
          try {
            console.log('AuthCallback: Processing successful auth with token and user data');
            
            // Verify the token works by getting fresh user data
            await AuthService.getUserByToken(authResult.token);
            
            // Refresh auth state in the context if available
            if (refreshAuth) {
              await refreshAuth();
            }
            
            // Call success callback
            onSuccess?.();
            
            // Show success state
            setSuccessMessage('Successfully authorized! Welcome, ' + authResult.user.display_name + ' (' + authResult.user.github_username + ').');
            setIsSuccess(true);
            
            console.log('AuthCallback: Showing success message, will redirect in 2 seconds');
            
            // Redirect to main app with a small delay to show success
            setTimeout(() => {
              console.log('AuthCallback: Redirecting to main app now');
              AuthService.redirectToMainApp();
            }, 2000);
          } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Token verification failed';
            setError(errorMsg);
            AuthService.handleAuthError(errorMsg);
            onError?.(errorMsg);
          }
        } else {
          // Check for success message in URL (from backend redirect)
          const successMessage = urlParams.get('message');
          console.log('AuthCallback: Checking for success message:', successMessage);
          
          if (successMessage && successMessage.includes('Successfully authorized')) {
            // This is a successful auth redirect from backend
            console.log('AuthCallback: Found success message, processing backend redirect');
            try {
              // Try to get user data from stored token
              const token = AuthService.getStoredToken();
              console.log('AuthCallback: Stored token exists:', !!token);
              
              if (token) {
                await AuthService.getUserByToken(token);
                
                // Refresh auth state in the context if available
                if (refreshAuth) {
                  await refreshAuth();
                }
                
                // Call success callback
                onSuccess?.();
                
                // Show success state
                setSuccessMessage('Successfully authorized! Welcome back.');
                setIsSuccess(true);
                
                console.log('AuthCallback: Backend redirect success, will redirect in 2 seconds');
                
                // Redirect to main app with a small delay to show success
                setTimeout(() => {
                  console.log('AuthCallback: Redirecting to main app from backend redirect');
                  AuthService.redirectToMainApp();
                }, 2000);
                return;
              }
            } catch (err) {
              console.error('Failed to verify stored token:', err);
            }
          }
          
          // No auth data in URL - check if we already have valid auth
          if (AuthService.isAuthenticated()) {
            try {
              const token = AuthService.getStoredToken();
              if (token) {
                await AuthService.getUserByToken(token);
                onSuccess?.();
                AuthService.redirectToMainApp();
                return;
              }
            } catch {
              // Token is invalid, clear it
              AuthService.logout();
            }
          }
          
          // No valid authentication found
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