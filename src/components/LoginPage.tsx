import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';

/**
 * LoginPage component handles GitHub OAuth login
 * Visual + copy refresh to highlight the new model monetization journey — functionality unchanged.
 */
export const LoginPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const githubAppInstallUrl = useMemo(() => {
    const explicitUrl = import.meta.env.VITE_GITHUB_APP_INSTALL_URL;
    if (explicitUrl) {
      return explicitUrl;
    }

    const appSlug = import.meta.env.VITE_GITHUB_APP_SLUG;
    if (appSlug) {
      return `https://github.com/apps/${appSlug}/installations/new`;
    }

    return 'https://github.com/apps/yudai/installations/new';
  }, []);

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

      // Use sessionStore login method (unchanged)
      await useSessionStore.getState().login();

    } catch (error) {
      console.error('[LoginPage] Login failed:', error);
      setError('Failed to initiate login. Please try again.');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(80%_60%_at_50%_0%,rgba(56,189,248,0.12),transparent_60%),radial-gradient(50%_40%_at_100%_20%,rgba(147,51,234,0.12),transparent_60%)]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6 leading-tight">
              Monetize your <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-violet-400">code, data & models</span>
            </h1>
            <p className="text-lg md:text-2xl text-zinc-300/90 mb-8 max-w-3xl mx-auto">
              Turn GitHub issues & PRs into a <span className="font-semibold text-white">personal AI agent</span>. Fine-tune at <span className="text-cyan-300">30/30 milestone</span>, then monetize when others use your agent.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <div className="bg-white/5 backdrop-blur-sm rounded-lg px-6 py-3 border border-white/10">
                <span className="text-zinc-200 text-sm">🧠 Base models: GPT-5, Claude, Qwen3-Coder, Grok & more</span>
              </div>
              <div className="bg-cyan-400/10 backdrop-blur-sm rounded-lg px-6 py-3 border border-cyan-300/20">
                <span className="text-cyan-100 text-sm">💡 Earn when collaborators rely on your personalized agent</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid lg:grid-cols-2 gap-12 items-start">

          {/* Left: Narrative & agent explainer */}
          <div className="space-y-8">

            {/* The Creator Journey */}
            <div className="bg-zinc-900/60 backdrop-blur-sm rounded-xl p-8 border border-zinc-800">
              <h2 className="text-2xl font-bold text-white mb-4">How It Works</h2>
              <ol className="space-y-4 text-zinc-300">
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />
                  <p><strong>Create & Solve:</strong> Generate GitHub issues and ship PRs with AI assistance.</p>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />
                  <p><strong>Hit 30/30:</strong> Unlock finetuning after 30 issues created & 30 merged.</p>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-violet-400" />
                  <p><strong>Share & Earn:</strong> Package your agent and monetize when others use it.</p>
                </li>
              </ol>
            </div>

            {/* Key Features */}
            <div className="bg-gradient-to-r from-cyan-400/10 to-violet-400/10 backdrop-blur-sm rounded-xl p-8 border border-cyan-300/20">
              <h2 className="text-2xl font-bold text-white mb-4">Key Benefits</h2>
              <div className="grid sm:grid-cols-2 gap-4 text-zinc-200">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-cyan-100">Usage-Based Payouts</p>
                  <p className="text-sm">Earn when others use your agent.</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-violet-100">Easy Sharing</p>
                  <p className="text-sm">Share with teammates & clients.</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-cyan-100">Clear Dashboard</p>
                  <p className="text-sm">Track usage and payouts.</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-violet-100">Full Control</p>
                  <p className="text-sm">You own your data & pricing.</p>
                </div>
              </div>
            </div>

            {/* What you get today */}
            <div className="bg-zinc-900/60 backdrop-blur-sm rounded-xl p-8 border border-zinc-800">
              <h2 className="text-2xl font-bold text-white mb-4">What's Available</h2>
              <div className="space-y-3 text-zinc-300">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mt-2" />
                  <p><strong>AI Issue Creation:</strong> Generate actionable GitHub issues.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mt-2" />
                  <p><strong>PR Assistance:</strong> Automated fix preparation.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-sky-500 rounded-full mt-2" />
                  <p><strong>Agent Marketplace:</strong> Monetize after 30/30.</p>
                </div>
              </div>
            </div>

          </div>

          {/* Right: Login & Install (functionality unchanged) */}
          <div className="lg:sticky lg:top-8">
            <div className="bg-zinc-900/70 backdrop-blur-sm rounded-xl p-8 border border-zinc-800 shadow-2xl">

              {/* Header */}
              <div className="text-center mb-6">
                <h2 className="text-2xl font-bold text-white mb-2">Join YudaiV3</h2>
                <p className="text-zinc-200">Complete two-step GitHub setup to unlock AI automations.</p>
              </div>

              {/* Two-step summary */}
              <div className="mb-6 rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-100">
                <p className="font-medium text-cyan-50">Two-step setup</p>
                <p className="text-cyan-100/90">1) Verify GitHub identity. 2) Install Yudai App for issue/PR creation.</p>
              </div>

              {/* Error Display (unchanged) */}
              {error && (
                <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}

              {/* Step 1: GitHub OAuth (button unchanged) */}
              <div className="mb-8 space-y-4">
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-cyan-300/40 bg-cyan-400/10 text-lg font-semibold text-cyan-100">1</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Verify GitHub Identity</h3>
                    <p className="text-sm text-zinc-200">Securely link your repos via OAuth.</p>
                  </div>
                </div>

                <button
                  onClick={handleGitHubLogin}
                  disabled={isLoading}
                  className="w-full bg-cyan-500 hover:bg-cyan-500/90 disabled:bg-cyan-500/50 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-3 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                      <span>Contacting GitHub...</span>
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
              </div>

              {/* Step 2: GitHub App Installation (link unchanged) */}
              <div className="mb-6 space-y-4">
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-violet-300/40 bg-violet-400/10 text-lg font-semibold text-violet-100">2</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Install Yudai GitHub App</h3>
                    <p className="text-sm text-zinc-200">Grant repo access for issues & PRs.</p>
                  </div>
                </div>

                <a
                  href={githubAppInstallUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center w-full rounded-lg border border-violet-200/50 bg-violet-400/10 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-violet-400/20"
                >
                  Install GitHub App
                </a>
              </div>

              {/* Feature bullets (kept; copy updated) */}
              <div className="space-y-3 mb-6">
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full" />
                  <span>AI analysis for Python & TypeScript</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-sky-500 rounded-full" />
                  <span>Generate GitHub issues & criteria</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-violet-500 rounded-full" />
                  <span>30/30 → finetune → monetize</span>
                </div>
              </div>

              {/* Discord CTA */}
              <div className="mb-6">
                <a
                  href="https://discord.gg/N95tf5Z6"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-3 w-full bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-400/30 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                  </svg>
                  <span>Join our Discord Community</span>
                </a>
              </div>

              {/* Footer */}
              <div className="pt-6 border-t border-zinc-800">
                <p className="text-xs text-zinc-400 text-center">
                  By signing in, you agree to our terms of service and privacy policy
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Bottom CTA */}
      <div className="border-t border-zinc-900">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h3 className="text-xl font-semibold text-white mb-4">
              Build & monetize your AI coding agent
            </h3>
            <div className="flex flex-wrap justify-center gap-4 text-sm text-zinc-400">
              <span>• GitHub-native</span>
              <span>• Creator-first</span>
              <span>• Usage insights</span>
              <span>• Personal workflows</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
