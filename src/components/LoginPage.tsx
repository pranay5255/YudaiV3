import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';

/**
 * LoginPage component handles GitHub OAuth login
 * Displays comprehensive product information and login functionality
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
    <div className="min-h-screen bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-secondary/10"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              Transform Your Code Into
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary">
                {' '}a Fortress of Reliability
              </span>
            </h1>
            <p className="text-xl md:text-2xl text-zinc-300 mb-8 max-w-3xl mx-auto">
              Solve critical issues instantly with AI-powered agents – perfect for solo-devs building the next web3 mini-app on Farcaster
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <div className="bg-zinc-800/50 backdrop-blur-sm rounded-lg px-6 py-3 border border-zinc-700">
                <span className="text-zinc-300 text-sm">🚀 Currently supports Python & TypeScript</span>
              </div>
              <div className="bg-primary/10 backdrop-blur-sm rounded-lg px-6 py-3 border border-primary/20">
                <span className="text-primary text-sm">⚡ Solidity & Deep Agents coming soon</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid lg:grid-cols-2 gap-12 items-start">

          {/* Product Information */}
          <div className="space-y-8">

            {/* The Pain */}
            <div className="bg-zinc-800/50 backdrop-blur-sm rounded-xl p-8 border border-zinc-700">
              <h2 className="text-2xl font-bold text-white mb-4">The Developer Struggle</h2>
              <div className="space-y-4 text-zinc-300">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p>Solo-devs wasting hours debugging critical issues in their repositories</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p>Web3 developers facing security vulnerabilities in smart contracts</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p>Hackers building mini-apps with complex integrations and rapid iteration needs</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p>Manual code review bottlenecks slowing down innovation</p>
                </div>
              </div>
            </div>

            {/* The Solution */}
            <div className="bg-zinc-800/50 backdrop-blur-sm rounded-xl p-8 border border-zinc-700">
              <h2 className="text-2xl font-bold text-white mb-4">How YudaiV3 Solves This</h2>
              <div className="space-y-4 text-zinc-300">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>AI-Powered Analysis:</strong> Automatically scans your repository for bugs, security issues, and performance bottlenecks</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Smart Issue Generation:</strong> Creates actionable GitHub issues with specific file references and solution steps</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Automated Resolution:</strong> Prepares detailed execution plans for SWE agents to implement fixes</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Focus on Innovation:</strong> Spend less time debugging, more time building amazing products</p>
                </div>
              </div>
            </div>

            {/* Upcoming Deep Agents */}
            <div className="bg-gradient-to-r from-primary/10 to-secondary/10 backdrop-blur-sm rounded-xl p-8 border border-primary/20">
              <h2 className="text-2xl font-bold text-white mb-4">🚀 Upcoming: Deep Agents</h2>
              <p className="text-zinc-300 mb-4">
                Our next evolution features advanced AI agents that will revolutionize code analysis:
              </p>
              <div className="space-y-3 text-sm text-zinc-300">
                <div className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Automated Code Inspection:</strong> LLM-powered analysis of codebase structure and patterns</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Intelligent Issue Generation:</strong> Structured GitHub issues with priorities, categories, and acceptance criteria</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>SWE Agent Preparation:</strong> Detailed execution plans for automated code fixes</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0"></div>
                  <p><strong>Scalable Architecture:</strong> Auto-scaling workloads with performance monitoring</p>
                </div>
              </div>
              <p className="text-xs text-zinc-400 mt-4">
                Currently scaffolded in backend/daifuUserAgent/architectAgent - coming soon!
              </p>
            </div>

          </div>

          {/* Login Section */}
          <div className="lg:sticky lg:top-8">
            <div className="bg-zinc-800/50 backdrop-blur-sm rounded-xl p-8 border border-zinc-700 shadow-2xl">

              {/* Header */}
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-white mb-2">Join YudaiV3</h2>
                <p className="text-zinc-300">Connect your GitHub to start solving issues with AI</p>
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
                className="w-full bg-primary hover:bg-primary/90 disabled:bg-primary/50 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-3 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>Connecting to GitHub...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clipRule="evenodd" />
                    </svg>
                    <span>Sign in with GitHub</span>
                  </>
                )}
              </button>

              {/* Features List */}
              <div className="mt-8 space-y-3">
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span>Analyze Python & TypeScript repositories</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <span>Generate actionable GitHub issues</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                  <span>Prepare solutions for automated fixes</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-400">
                  <div className="w-2 h-2 bg-zinc-500 rounded-full"></div>
                  <span>Solidity & Deep Agents - Coming Soon</span>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-8 pt-6 border-t border-zinc-700">
                <p className="text-xs text-zinc-500 text-center">
                  By signing in, you agree to our terms of service and privacy policy
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Bottom CTA */}
      <div className="border-t border-zinc-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h3 className="text-xl font-semibold text-white mb-4">
              Ready to transform your development workflow?
            </h3>
            <p className="text-zinc-400 mb-6">
              Join the future of AI-powered code analysis and focus on what matters: building amazing products.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm text-zinc-500">
              <span>• Built for solo-devs & web3 hackers</span>
              <span>• GitHub-native integration</span>
              <span>• Privacy-first approach</span>
              <span>• Continuous improvement</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};