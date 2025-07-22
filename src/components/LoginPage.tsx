import React, { useState } from 'react';
import { Github, Shield, Zap, Code, Cat, GitBranch, MessageSquare, FileText } from 'lucide-react';
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
      <div className="max-w-4xl w-full space-y-8">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-primary rounded-2xl flex items-center justify-center mb-6">
            <Cat className="h-10 w-10 text-white" />
          </div>
          <h2 className="text-4xl font-bold text-fg">
            Welcome to YudaiV3
          </h2>
          <p className="mt-2 text-lg text-fg/70">
            Your AI-powered cat coding assistant 🐱‍💻
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Left Column - Features & Agent Info */}
          <div className="space-y-6">
            {/* Agent Capabilities */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Cat className="h-5 w-5 text-primary mr-2" />
                Meet Your Cat Coding Agent
              </h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <MessageSquare className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Smart Conversation</p>
                    <p className="text-xs text-fg/60">Engage in natural chat about your codebase and development challenges</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <FileText className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Detailed Task Creation</p>
                    <p className="text-xs text-fg/60">Transform conversations into structured, actionable development tasks</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <GitBranch className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">GitHub Issue Generation</p>
                    <p className="text-xs text-fg/60">Automatically create comprehensive GitHub issues with context and requirements</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <Code className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Coder Model Integration</p>
                    <p className="text-xs text-fg/60">Seamlessly hand off tasks to advanced coding models for implementation</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Security Features */}
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
          </div>

          {/* Right Column - Fun Facts */}
          <div className="space-y-6">
            {/* Cat Facts */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Cat className="h-5 w-5 text-primary mr-2" />
                Fun Cat Facts 🐱
              </h3>
              <div className="space-y-3">
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Purr-fect Code:</span> Cats can make over 100 different vocal sounds, just like how we can write code in 100+ programming languages!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Nine Lives Debugging:</span> Cats can rotate their ears 180 degrees - perfect for listening to multiple bug reports at once!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Whisker Navigation:</span> A cat's whiskers help them navigate in the dark, just like our AI helps navigate complex codebases!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Cat-astrophic Testing:</span> Cats spend 70% of their lives sleeping - but our cat agent works 24/7 to help you code!
                </div>
              </div>
            </div>

            {/* Coding Facts */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Code className="h-5 w-5 text-primary mr-2" />
                Cool Coding Facts 💻
              </h3>
              <div className="space-y-3">
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">First Bug:</span> The first computer bug was an actual bug - a moth found in Harvard's Mark II computer in 1947!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Git Magic:</span> Git was created by Linus Torvalds in just 2 weeks to manage Linux kernel development!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Python's Name:</span> Python was named after Monty Python, not the snake - Guido van Rossum was reading Monty Python scripts!
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">JavaScript:</span> JavaScript was created in just 10 days by Brendan Eich at Netscape in 1995!
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Login Button */}
        <div className="space-y-4 max-w-md mx-auto">
          <button
            onClick={handleLogin}
            disabled={isLoading || isLoggingIn}
            className="group relative w-full flex justify-center items-center py-4 px-6 border border-transparent text-lg font-medium rounded-xl text-white bg-primary hover:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
          >
            {isLoggingIn ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                Redirecting to GitHub...
              </>
            ) : (
              <>
                <Github className="h-6 w-6 mr-3" />
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