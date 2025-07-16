import React, { useState } from 'react';
import { Github, Shield, Zap, Code } from 'lucide-react';
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
      <div className="max-w-md w-full space-y-8">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-16 w-16 bg-primary rounded-2xl flex items-center justify-center mb-6">
            <Code className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-fg">
            Welcome to YudaiV3
          </h2>
          <p className="mt-2 text-sm text-fg/70">
            Your AI-powered development assistant
          </p>
        </div>

        {/* Features */}
        <div className="space-y-4">
          <div className="flex items-center space-x-3 text-fg/80">
            <Shield className="h-5 w-5 text-primary" />
            <span className="text-sm">Secure GitHub OAuth authentication</span>
          </div>
          <div className="flex items-center space-x-3 text-fg/80">
            <Zap className="h-5 w-5 text-primary" />
            <span className="text-sm">AI-powered code analysis and chat</span>
          </div>
          <div className="flex items-center space-x-3 text-fg/80">
            <Github className="h-5 w-5 text-primary" />
            <span className="text-sm">Seamless GitHub integration</span>
          </div>
        </div>

        {/* Login Button */}
        <div className="space-y-4">
          <button
            onClick={handleLogin}
            disabled={isLoading || isLoggingIn}
            className="group relative w-full flex justify-center items-center py-3 px-4 border border-transparent text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
          >
            {isLoggingIn ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Redirecting to GitHub...
              </>
            ) : (
              <>
                <Github className="h-5 w-5 mr-2" />
                Sign in with GitHub
              </>
            )}
          </button>

          <p className="text-xs text-center text-fg/50">
            By signing in, you agree to our terms of service and privacy policy
          </p>
        </div>

        {/* Additional Info */}
        <div className="text-center">
          <p className="text-xs text-fg/40">
            Need help? Contact support at support@yudai.dev
          </p>
        </div>
      </div>
    </div>
  );
}; 