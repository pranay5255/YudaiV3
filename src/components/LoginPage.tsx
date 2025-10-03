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
              YudaiV3 turns your GitHub issues & merged PRs into a <span className="font-semibold text-white">personal model marketplace</span>.
              Finetune after your <span className="text-cyan-300">30 issues created</span> & <span className="text-cyan-300">30 issues merged</span> milestone, share your agent with trusted teams, and unlock new ways to earn from the work you already ship.
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

          {/* Left: Narrative & Marketplace explainer */}
          <div className="space-y-8">

            {/* The Creator Journey */}
            <div className="bg-zinc-900/60 backdrop-blur-sm rounded-xl p-8 border border-zinc-800">
              <h2 className="text-2xl font-bold text-white mb-4">Your Path to a Monetized Coding Agent</h2>
              <ol className="space-y-5 text-zinc-300">
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />
                  <p><strong>Compose & Solve:</strong> Use YudaiV3 to create GitHub issues and ship PRs with AI assistance. Your dataset grows as issues are merged.</p>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-cyan-400" />
                  <p><strong>Unlock Finetune at 30/30:</strong> Hit <em>30 issues created</em> & <em>30 merged</em> to trigger a guided finetune from your repo-specific history.</p>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-violet-400" />
                  <p><strong>Share Your Agent:</strong> Package your agent with clear documentation so peers can pull it into their workflows without manual setup.</p>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-violet-400" />
                  <p><strong>Monetize Usage:</strong> Earn when others rely on your hosted model, while you keep full visibility into performance and updates.</p>
                </li>
              </ol>
            </div>

            {/* Marketplace Momentum */}
            <div className="bg-gradient-to-r from-cyan-400/10 to-violet-400/10 backdrop-blur-sm rounded-xl p-8 border border-cyan-300/20">
              <h2 className="text-2xl font-bold text-white mb-4">Model Marketplace Momentum</h2>
              <div className="grid sm:grid-cols-2 gap-6 text-zinc-200">
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-cyan-100">Aligned Incentives</p>
                  <p className="text-sm">Usage-based payouts keep your agent improving while rewarding the expertise already baked into your repos.</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-violet-100">Boost Discovery</p>
                  <p className="text-sm">Highlight your agent inside Yudai’s marketplace so other builders can subscribe and benefit from your playbooks.</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-cyan-100">Clear Billing</p>
                  <p className="text-sm">Simple dashboards help you track usage, payouts, and the repositories your agent supports.</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-violet-100">Creator-First Design</p>
                  <p className="text-sm">Your repo data → your model → your monetization plan. You stay in control of access, pricing, and version updates.</p>
                </div>
              </div>
              <p className="text-xs text-zinc-400 mt-4">Note: All marketplace mechanics are additive to your existing GitHub workflow — no changes to your repos or auth required.</p>
            </div>

            {/* What you get today */}
            <div className="bg-zinc-900/60 backdrop-blur-sm rounded-xl p-8 border border-zinc-800">
              <h2 className="text-2xl font-bold text-white mb-4">What’s Live Today</h2>
              <div className="space-y-4 text-zinc-300">
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mt-2" />
                  <p><strong>AI Issue Composer:</strong> Generate crisp, actionable GitHub issues with file diffs & acceptance criteria.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full mt-2" />
                  <p><strong>PR Assist:</strong> Plan and prepare fixes for automated agents — you stay in control of merges.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-sky-500 rounded-full mt-2" />
                  <p><strong>Marketplace Preview:</strong> Monetize your agent after the 30/30 milestone with ready-to-launch subscription rails.</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-2 h-2 bg-zinc-500 rounded-full mt-2" />
                  <p>Solidity agents & deeper repo orchestration — <em>coming soon</em>.</p>
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
                <p className="text-zinc-200">Complete the two-step GitHub onboarding to unlock AI automations & the model marketplace.</p>
              </div>

              {/* Two-step summary */}
              <div className="mb-6 rounded-lg border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-100">
                <p className="font-medium text-cyan-50">Two-step setup</p>
                <p className="text-cyan-100/90">1) Verify your GitHub identity. 2) Install the Yudai GitHub App so the agent can create issues and pull requests on your behalf.</p>
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
                    <h3 className="text-lg font-semibold text-white">Verify your GitHub identity</h3>
                    <p className="text-sm text-zinc-200">OAuth lets us securely link your repos. Revoke access anytime in GitHub settings.</p>
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
              <div className="mb-8 space-y-4">
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-violet-300/40 bg-violet-400/10 text-lg font-semibold text-violet-100">2</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Install the Yudai GitHub App</h3>
                    <p className="text-sm text-zinc-200">Grant repo access so Yudai can create issues & pull requests. This powers your 30/30 milestone and future finetunes.</p>
                  </div>
                </div>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <a
                    href={githubAppInstallUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center rounded-lg border border-violet-200/50 bg-violet-400/10 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-violet-400/20"
                  >
                    Install GitHub App
                  </a>
                  <p className="text-xs text-zinc-200">
                    Install to your personal account or an organization (admin permissions required).
                  </p>
                </div>

                <div className="rounded-lg border border-amber-300/30 bg-amber-500/10 p-4 text-xs text-amber-100">
                  <p className="font-medium text-amber-50">Why this matters</p>
                  <p className="text-amber-100/90">
                    The App unlocks repository triage, automated issue drafting, and PR prep. It’s also how we verify your 30/30 milestone for model monetization.
                  </p>
                </div>
              </div>

              {/* Feature bullets (kept; copy updated) */}
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full" />
                  <span>AI analysis for Python & TypeScript repos</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-sky-500 rounded-full" />
                  <span>Generate actionable GitHub issues & acceptance criteria</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-200">
                  <div className="w-2 h-2 bg-violet-500 rounded-full" />
                  <span>Finetune at 30/30 → share your agent → earn from real usage</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <div className="w-2 h-2 bg-zinc-500 rounded-full" />
                  <span>Solidity & Deep Agents — Coming Soon</span>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-8 pt-6 border-t border-zinc-800">
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
              Ready to list your first model on the marketplace?
            </h3>
            <p className="text-zinc-300 mb-6">
              Ship issues faster, hit 30/30, finetune, and monetize a personal agent that reflects how you already build.
            </p>
            <div className="flex flex-wrap justify-center gap-4 text-sm text-zinc-400">
              <span>• GitHub-native</span>
              <span>• Creator-first monetization</span>
              <span>• Transparent usage insights</span>
              <span>• Built for personal workflows</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
