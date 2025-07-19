import React, { useState } from 'react';
import { Github, Heart, Coffee } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = async () => {
    try {
      setIsLoggingIn(true);
      await login();
    } catch (error) {
      console.error('Login failed:', error);
      setIsLoggingIn(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-bg via-bg/95 to-zinc-900 flex items-center justify-center p-4">
      <div className="max-w-sm w-full space-y-6">
        {/* Cat-themed Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-12 w-12 bg-primary rounded-full flex items-center justify-center mb-4">
            <span className="text-2xl">🐱</span>
          </div>
          <h2 className="text-2xl font-bold text-fg">
            YudaiV3
          </h2>
          <p className="text-sm text-fg/70">
            Where cats and code collide
          </p>
        </div>

        {/* Fun Cat Facts */}
        <div className="space-y-3 text-center">
          <div className="text-xs text-fg/60">
            <p>🐾 Cats are natural debuggers - they always find the warmest spot</p>
            <p>😸 Like cats, good code is curious and playful</p>
            <p>💤 Cats know the importance of rest - so do great developers</p>
          </div>
        </div>

        {/* Login Button */}
        <div className="space-y-3">
          <button
            onClick={handleLogin}
            disabled={isLoading || isLoggingIn}
            className="group relative w-full flex justify-center items-center py-3 px-4 border border-transparent text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            {isLoggingIn ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Redirecting...
              </>
            ) : (
              <>
                <Github className="h-4 w-4 mr-2" />
                Sign in with GitHub
              </>
            )}
          </button>

          <div className="flex items-center justify-center space-x-2 text-xs text-fg/40">
            <Coffee className="h-3 w-3" />
            <span>Powered by catnip and caffeine</span>
            <Heart className="h-3 w-3 text-red-400" />
          </div>
        </div>
      </div>
    </div>
  );
}; 