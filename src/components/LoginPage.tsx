import React, { useState } from 'react';
import { Github, Shield, Zap, Code, GitBranch, MessageSquare, FileText, Users, TrendingUp, Target, Sparkles } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

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
      <div className="max-w-6xl w-full space-y-8">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-primary rounded-2xl flex items-center justify-center mb-6">
            <Sparkles className="h-10 w-10 text-white" />
          </div>
          <h2 className="text-4xl font-bold text-fg">
            Welcome to YudaiV3
          </h2>
          <p className="mt-2 text-lg text-fg/70">
            Transform context into actionable GitHub issues and pull requests
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left Column - Value Proposition */}
          <div className="space-y-6">
            {/* Hero Section */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Target className="h-5 w-5 text-primary mr-2" />
                Bridge Ideas to Implementation
              </h3>
              <p className="text-fg/80 text-sm leading-relaxed">
                YudaiV3 is your AI-powered coding agent that transforms raw context—chat summaries, CSVs, PDFs, or plain text—into concise, actionable GitHub issues and pull requests. Perfect for teams looking to streamline their development workflow.
              </p>
            </div>

            {/* Target Audience */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Users className="h-5 w-5 text-primary mr-2" />
                Built for Modern Teams
              </h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <Code className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Software Developers</p>
                    <p className="text-xs text-fg/60">Generate feature scaffolds and bug fixes from high-level descriptions</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <TrendingUp className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Product Managers & Designers</p>
                    <p className="text-xs text-fg/60">Convert user stories and feedback into developer-ready GitHub issues</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <FileText className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Data Analysts & Scientists</p>
                    <p className="text-xs text-fg/60">Transform data-driven insights into actionable engineering tasks</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <GitBranch className="h-5 w-5 text-primary mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-fg">Technical Teams</p>
                    <p className="text-xs text-fg/60">Standardize and automate high-quality, bite-sized pull requests</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Key Features */}
            <div className="space-y-4">
              <div className="flex items-center space-x-3 text-fg/80">
                <Shield className="h-5 w-5 text-primary" />
                <span className="text-sm">Secure GitHub OAuth authentication</span>
              </div>
              <div className="flex items-center space-x-3 text-fg/80">
                <Zap className="h-5 w-5 text-primary" />
                <span className="text-sm">AI-powered context analysis and issue generation</span>
              </div>
              <div className="flex items-center space-x-3 text-fg/80">
                <MessageSquare className="h-5 w-5 text-primary" />
                <span className="text-sm">Natural language conversation with your codebase</span>
              </div>
            </div>
          </div>

          {/* Right Column - How It Works */}
          <div className="space-y-6">
            {/* How It Works */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Zap className="h-5 w-5 text-primary mr-2" />
                How It Works
              </h3>
              <div className="space-y-4">
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-xs font-bold text-white">1</div>
                  <div>
                    <p className="text-sm font-medium text-fg">Provide Context</p>
                    <p className="text-xs text-fg/60">Upload files (CSV, PDF, text) or input chat summaries via the web interface</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-xs font-bold text-white">2</div>
                  <div>
                    <p className="text-sm font-medium text-fg">Generate Issues</p>
                    <p className="text-xs text-fg/60">YudaiV3 analyzes input and creates detailed GitHub issues with actionable tasks</p>
                  </div>
                </div>
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-6 h-6 bg-primary rounded-full flex items-center justify-center text-xs font-bold text-white">3</div>
                  <div>
                    <p className="text-sm font-medium text-fg">Create Pull Requests</p>
                    <p className="text-xs text-fg/60">Based on issues, generate small, manageable PRs with code suggestions</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Example Use Case */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <MessageSquare className="h-5 w-5 text-primary mr-2" />
                Example Workflow
              </h3>
              <div className="space-y-3">
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Input:</span> CSV with bug reports: <code className="bg-zinc-700 px-1 rounded text-xs">bug_id,description,priority,file</code>
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Output:</span> GitHub issue "Fix Login Button Misalignment" with description, priority tag, and reference to <code className="bg-zinc-700 px-1 rounded text-xs">src/components/Login.js</code>
                </div>
                <div className="text-sm text-fg/80">
                  <span className="font-medium text-primary">Result:</span> Pull request with suggested CSS fixes and implementation details
                </div>
              </div>
            </div>

            {/* Open Source */}
            <div className="bg-zinc-800/50 rounded-xl p-6 border border-zinc-700/50">
              <h3 className="text-xl font-semibold text-fg mb-4 flex items-center">
                <Github className="h-5 w-5 text-primary mr-2" />
                Open Source
              </h3>
              <p className="text-sm text-fg/80 mb-4">
                YudaiV3 is an early-stage open-source project. Contribute, star, or fork to help us grow!
              </p>
              <a 
                href="https://github.com/pranay5255/YudaiV3" 
                target="_blank" 
                rel="noopener noreferrer"
                className="inline-flex items-center text-primary hover:text-primary/80 text-sm font-medium transition-colors"
              >
                <Github className="h-4 w-4 mr-2" />
                View on GitHub
              </a>
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
            Need help? Contact support at support@yudai.app
          </p>
        </div>
      </div>
    </div>
  );
}; 