import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';

/**
 * LoginPage component handles GitHub OAuth login
 * YudaiV3: Context-engineered coding agent for review-ready PRs
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
    <div className="min-h-screen bg-[#0a0a0b] text-[#f4f4f5] selection:bg-amber-500/30">
      {/* Subtle texture overlay */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Hero Section */}
      <div className="relative overflow-hidden border-b border-[#2a2a2e]">
        {/* Ambient glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(245,158,11,0.08),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_100%_0%,rgba(34,211,238,0.05),transparent_50%)]" />

        <div className="relative max-w-6xl mx-auto px-6 lg:px-8 pt-20 pb-16">
          <div className="max-w-3xl">
            {/* Eyebrow */}
            <div className="flex items-center gap-3 mb-6">
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#1a1a1d] border border-[#2a2a2e] text-xs font-mono text-[#a1a1aa]">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                context-engineered agent
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.1] mb-6">
              <span className="text-[#f4f4f5]">Chat summaries,</span>
              <br />
              <span className="text-[#f4f4f5]">file insights,</span>
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-amber-500">review-ready PRs.</span>
            </h1>

            {/* Subheadline */}
            <p className="text-lg sm:text-xl text-[#a1a1aa] leading-relaxed max-w-2xl mb-8">
              YudaiV3 connects to your GitHub repo and turns curated context into small,
              focused pull requests—with full auditable trajectories for every decision.
            </p>

            {/* Value props */}
            <div className="flex flex-wrap gap-3">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#111113] border border-[#2a2a2e]">
                <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                </svg>
                <span className="text-sm text-[#a1a1aa]">File dependency mapping</span>
              </div>
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#111113] border border-[#2a2a2e]">
                <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                </svg>
                <span className="text-sm text-[#a1a1aa]">Curated chat context</span>
              </div>
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#111113] border border-[#2a2a2e]">
                <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm text-[#a1a1aa]">Auditable trajectories</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-6 lg:px-8 py-16">
        <div className="grid lg:grid-cols-5 gap-12 lg:gap-16">

          {/* Left: Features (3 columns) */}
          <div className="lg:col-span-3 space-y-10">

            {/* How It Works */}
            <div>
              <h2 className="text-sm font-mono text-[#71717a] uppercase tracking-wider mb-6">How it works</h2>
              <div className="space-y-6">
                {[
                  {
                    step: '01',
                    title: 'Connect',
                    description: 'Link your GitHub repository. YudaiV3 maps file dependencies and extracts structural context automatically.',
                    color: 'cyan'
                  },
                  {
                    step: '02',
                    title: 'Converse',
                    description: 'Chat naturally about your codebase. Context cards capture and distill key insights from each conversation.',
                    color: 'amber'
                  },
                  {
                    step: '03',
                    title: 'Generate',
                    description: 'The agent produces small, focused PRs from your curated context—scoped for easy review and quick iteration.',
                    color: 'emerald'
                  },
                  {
                    step: '04',
                    title: 'Audit',
                    description: 'Every decision is logged with full trajectory. Trace exactly how context informed each code change.',
                    color: 'violet'
                  }
                ].map((item) => (
                  <div key={item.step} className="flex gap-5">
                    <div className="flex-shrink-0">
                      <span className={`inline-flex items-center justify-center w-10 h-10 rounded-lg bg-${item.color}-500/10 border border-${item.color}-500/20 font-mono text-sm text-${item.color}-400`}
                        style={{
                          backgroundColor: item.color === 'cyan' ? 'rgba(34,211,238,0.1)' :
                                          item.color === 'amber' ? 'rgba(245,158,11,0.1)' :
                                          item.color === 'emerald' ? 'rgba(16,185,129,0.1)' :
                                          'rgba(139,92,246,0.1)',
                          borderColor: item.color === 'cyan' ? 'rgba(34,211,238,0.2)' :
                                       item.color === 'amber' ? 'rgba(245,158,11,0.2)' :
                                       item.color === 'emerald' ? 'rgba(16,185,129,0.2)' :
                                       'rgba(139,92,246,0.2)',
                          color: item.color === 'cyan' ? '#22d3ee' :
                                 item.color === 'amber' ? '#f59e0b' :
                                 item.color === 'emerald' ? '#10b981' :
                                 '#8b5cf6'
                        }}
                      >
                        {item.step}
                      </span>
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-[#f4f4f5] mb-1">{item.title}</h3>
                      <p className="text-[#a1a1aa] leading-relaxed">{item.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Features Grid */}
            <div className="pt-6 border-t border-[#1a1a1d]">
              <h2 className="text-sm font-mono text-[#71717a] uppercase tracking-wider mb-6">Capabilities</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                {[
                  { title: 'File Dependency Analysis', desc: 'Understand how your codebase connects' },
                  { title: 'Chat-to-Context Cards', desc: 'Distill conversations into actionable insights' },
                  { title: 'Small, Focused PRs', desc: 'Scoped changes that are easy to review' },
                  { title: 'Full Trajectory Logs', desc: 'Audit every decision the agent makes' },
                  { title: 'Analytics Dashboard', desc: 'Track patterns and insights over time' },
                  { title: 'GitHub-Native', desc: 'Works seamlessly with your existing workflow' },
                ].map((feature) => (
                  <div key={feature.title} className="p-4 rounded-lg bg-[#111113] border border-[#1a1a1d] hover:border-[#2a2a2e] transition-colors">
                    <h3 className="text-sm font-medium text-[#f4f4f5] mb-1">{feature.title}</h3>
                    <p className="text-xs text-[#71717a]">{feature.desc}</p>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Right: Login Panel (2 columns) */}
          <div className="lg:col-span-2">
            <div className="lg:sticky lg:top-8">
              <div className="rounded-xl bg-[#111113] border border-[#2a2a2e] p-6 sm:p-8 shadow-2xl shadow-black/20">

                {/* Header */}
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-[#f4f4f5] mb-2">Get Started</h2>
                  <p className="text-sm text-[#a1a1aa]">Connect your GitHub to start generating context-aware PRs.</p>
                </div>

                {/* Two-step indicator */}
                <div className="mb-6 p-3 rounded-lg bg-amber-500/5 border border-amber-500/10">
                  <p className="text-xs font-mono text-amber-400/80 mb-1">TWO-STEP SETUP</p>
                  <p className="text-sm text-[#a1a1aa]">Authenticate with GitHub, then install the app for repo access.</p>
                </div>

                {/* Error Display */}
                {error && (
                  <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <p className="text-red-400 text-sm">{error}</p>
                  </div>
                )}

                {/* Step 1: GitHub OAuth */}
                <div className="mb-6">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-xs font-mono text-cyan-400">1</span>
                    <span className="text-sm font-medium text-[#f4f4f5]">Sign in with GitHub</span>
                  </div>

                  <button
                    onClick={handleGitHubLogin}
                    disabled={isLoading}
                    className="w-full bg-[#f4f4f5] hover:bg-white disabled:bg-[#a1a1aa] text-[#0a0a0b] font-medium py-3.5 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-3 shadow-lg hover:shadow-xl hover:-translate-y-0.5 disabled:translate-y-0 disabled:shadow-lg"
                  >
                    {isLoading ? (
                      <>
                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-[#0a0a0b]/20 border-t-[#0a0a0b]" />
                        <span>Connecting...</span>
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clipRule="evenodd" />
                        </svg>
                        <span>Sign in with GitHub</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Step 2: GitHub App Installation */}
                <div className="mb-6">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-mono text-amber-400">2</span>
                    <span className="text-sm font-medium text-[#f4f4f5]">Install GitHub App</span>
                  </div>

                  <a
                    href={githubAppInstallUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center w-full rounded-lg border border-[#2a2a2e] bg-[#1a1a1d] hover:bg-[#222225] px-6 py-3 text-sm font-medium text-[#f4f4f5] transition-colors"
                  >
                    Install GitHub App
                  </a>
                </div>

                {/* Feature bullets */}
                <div className="space-y-2.5 mb-6 py-4 border-y border-[#1a1a1d]">
                  {[
                    'Map file dependencies automatically',
                    'Generate focused, review-ready PRs',
                    'Full audit trail for every change'
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-2.5 text-sm text-[#a1a1aa]">
                      <svg className="w-4 h-4 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>

                {/* Discord CTA */}
                <a
                  href="https://discord.gg/U96mwKmJ"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2.5 w-full bg-[#5865F2]/10 hover:bg-[#5865F2]/20 border border-[#5865F2]/20 text-[#f4f4f5] font-medium py-3 px-6 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                  </svg>
                  <span>Join Discord Community</span>
                </a>

                {/* Footer */}
                <div className="mt-6 pt-4 border-t border-[#1a1a1d]">
                  <p className="text-xs text-[#71717a] text-center">
                    By signing in, you agree to our terms of service and privacy policy
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Bottom CTA */}
      <div className="border-t border-[#1a1a1d]">
        <div className="max-w-4xl mx-auto px-6 lg:px-8 py-12">
          <div className="text-center">
            <p className="text-[#a1a1aa] mb-4">
              <span className="text-[#f4f4f5] font-medium">Context-engineered coding agent</span> that turns your conversations and file insights into small, review-ready pull requests.
            </p>
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-[#71717a]">
              <span className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-cyan-500" />
                File dependencies
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-amber-500" />
                Chat summaries
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-emerald-500" />
                Auditable trajectories
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-violet-500" />
                Review-ready PRs
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
