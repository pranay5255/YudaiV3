import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';

/**
 * LoginPage component handles GitHub OAuth login
 * Redesigned to emphasize synthetic datasets, distillation, and benchmarking.
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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(80%_60%_at_50%_0%,rgba(99,102,241,0.10),transparent_60%),radial-gradient(50%_40%_at_100%_20%,rgba(59,130,246,0.08),transparent_60%)]" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6 leading-tight">
              Create <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">coding datasets for your model</span>
            </h1>
            <p className="text-lg md:text-xl text-slate-300/90 mb-8 max-w-3xl mx-auto">
              Yudai generates CI-verified synthetic datasets from your GitHub issues—perfect for training, distilling, and benchmarking your coding models.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <div className="bg-white/5 backdrop-blur-sm rounded-lg px-6 py-3 border border-white/10">
                <span className="text-slate-200 text-sm">🎯 High-quality training data from real repos</span>
              </div>
              <div className="bg-blue-400/10 backdrop-blur-sm rounded-lg px-6 py-3 border border-blue-300/20">
                <span className="text-blue-100 text-sm">🧬 Best-of-N sampling + test verification</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid lg:grid-cols-2 gap-12 items-start">

          {/* Left: Core pillars and features */}
          <div className="space-y-8">

            {/* Three Pillars */}
            <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl p-8 border border-slate-800">
              <h2 className="text-2xl font-bold text-white mb-6">Build Your Training Dataset</h2>
              <div className="space-y-4 text-slate-300">
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-emerald-400" />
                  <p><strong className="text-emerald-300">Generate Datasets</strong> — Teacher LLMs produce multiple candidate fixes; CI keeps only passing diffs with step-by-step reasoning traces.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-blue-400" />
                  <p><strong className="text-blue-300">Distill Models</strong> — Use your dataset for supervised KD (forward KL) → on-policy refinement (reverse KL) → balanced Jeffreys.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-indigo-400" />
                  <p><strong className="text-indigo-300">Benchmark Performance</strong> — Track pass rate, reasoning alignment, and code quality across runs—against your own repos.</p>
                </div>
              </div>
            </div>

            {/* How it works */}
            <div className="bg-slate-900/60 backdrop-blur-sm rounded-xl p-8 border border-slate-800">
              <h2 className="text-2xl font-bold text-white mb-4">How it works</h2>
              <ol className="space-y-3 text-slate-300">
                <li className="flex items-start gap-3">
                  <span className="font-mono text-blue-400 font-semibold min-w-[1.5rem]">1.</span>
                  <p><strong>Ingest</strong> your repo + issues → generate N candidate patches per issue.</p>
                </li>
                <li className="flex items-start gap-3">
                  <span className="font-mono text-blue-400 font-semibold min-w-[1.5rem]">2.</span>
                  <p><strong>Verify & select</strong> via tests, lint/style, and reasoning coherence.</p>
                </li>
                <li className="flex items-start gap-3">
                  <span className="font-mono text-blue-400 font-semibold min-w-[1.5rem]">3.</span>
                  <p><strong>Train & evaluate</strong> the student; iterate where it fails (teacher-guided).</p>
                </li>
              </ol>
            </div>

            {/* Feature Grid */}
            <div className="bg-gradient-to-r from-blue-400/10 to-indigo-400/10 backdrop-blur-sm rounded-xl p-8 border border-blue-300/20">
              <h2 className="text-2xl font-bold text-white mb-4">Dataset Creation Features</h2>
              <div className="space-y-3 text-slate-200">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>Automated dataset generation</strong> from issues → PR diffs (CI-verified)</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-blue-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>Reasoning traces included</strong> for better model training</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>Best-of-N sampling</strong> ensures highest quality examples</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>Ready for distillation</strong> (forward KL, reverse KL, Jeffreys)</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>On-policy feedback loops</strong> for continuous improvement</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full mt-2" />
                  <p className="text-sm"><strong>Quality metrics</strong>: test pass rate, style checks, trace alignment</p>
                </div>
              </div>
            </div>

          </div>

          {/* Right: Login & Install (functionality unchanged) */}
          <div className="lg:sticky lg:top-8">
            <div className="bg-slate-900/70 backdrop-blur-sm rounded-xl p-8 border border-slate-800 shadow-2xl">

              {/* Header */}
              <div className="text-center mb-6">
                <h2 className="text-2xl font-bold text-white mb-2">Start Creating Datasets</h2>
                <p className="text-slate-200">Two-step GitHub setup to generate coding datasets from your repos.</p>
              </div>

              {/* Two-step summary */}
              <div className="mb-6 rounded-lg border border-blue-300/30 bg-blue-400/10 px-4 py-3 text-sm text-blue-100">
                <p className="font-medium text-blue-50">Two-step setup</p>
                <p className="text-blue-100/90">1) Authenticate with GitHub. 2) Install Yudai App for repo access.</p>
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
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-blue-300/40 bg-blue-400/10 text-lg font-semibold text-blue-100">1</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Sign in with GitHub</h3>
                    <p className="text-sm text-slate-200">Authenticate and link your repositories.</p>
                  </div>
                </div>

                <button
                  onClick={handleGitHubLogin}
                  disabled={isLoading}
                  className="w-full bg-blue-500 hover:bg-blue-500/90 disabled:bg-blue-500/50 text-white font-medium py-4 px-6 rounded-lg transition-all duration-200 flex items-center justify-center space-x-3 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
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
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-indigo-300/40 bg-indigo-400/10 text-lg font-semibold text-indigo-100">2</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Install GitHub App</h3>
                    <p className="text-sm text-slate-200">Grant Yudai access to create issues & PRs.</p>
                  </div>
                </div>

                <a
                  href={githubAppInstallUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center w-full rounded-lg border border-indigo-200/50 bg-indigo-400/10 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-indigo-400/20"
                >
                  Install GitHub App
                </a>
              </div>

              {/* Feature bullets */}
              <div className="space-y-3 mb-6">
                <div className="flex items-center gap-3 text-sm text-slate-200">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full" />
                  <span>Auto-generate training datasets from your code</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-slate-200">
                  <div className="w-2 h-2 bg-blue-400 rounded-full" />
                  <span>CI-verified quality for model training</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-slate-200">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full" />
                  <span>Reasoning traces for better distillation</span>
                </div>
              </div>

              {/* Discord CTA */}
              <div className="mb-6">
                <a
                  href="https://discord.gg/U96mwKmJ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-3 w-full bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-400/30 text-white font-medium py-3 px-6 rounded-lg transition-all duration-200"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                  </svg>
                  <span>Join Discord Community</span>
                </a>
              </div>

              {/* Footer */}
              <div className="pt-6 border-t border-slate-800">
                <p className="text-xs text-slate-400 text-center">
                  By signing in, you agree to our terms of service and privacy policy
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Bottom CTA */}
      <div className="border-t border-slate-900">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <p className="text-slate-300 mb-4">
              Create <strong className="text-white">high-quality coding datasets for training your models</strong>—automatically generated from your repos, no manual labeling required.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm text-slate-400">
              <span>• GitHub-native dataset generation</span>
              <span>• CI-verified quality</span>
              <span>• Reasoning traces included</span>
              <span>• Ready for training & distillation</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
