import React from 'react';
import { useShallow } from 'zustand/react/shallow';
import {
  Bot,
  CreditCard,
  Database,
  MessageCircle,
  Route,
  User,
  Zap,
} from 'lucide-react';
import { TabType } from '../types';
import { UserProfile } from './UserProfile';
import { useAuth } from '../hooks/useAuth';
import { useSessionStore } from '../stores/sessionStore';

interface TopBarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const tabs: Array<{
  id: TabType;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { id: 'chat', label: 'Chat', icon: MessageCircle },
  { id: 'context', label: 'Context', icon: CreditCard },
  { id: 'ideas', label: 'Trajectory', icon: Route },
  { id: 'solve', label: 'Execution', icon: Zap },
];

const sessionStatusLabel: Record<string, string> = {
  no_repo: 'No Repo',
  awaiting_session: 'Pending Session',
  creating_session: 'Creating Session',
  ready: 'Ready',
  sending: 'Sending',
  error: 'Error',
};

const sessionStatusTone: Record<string, string> = {
  no_repo: 'text-muted border-border bg-bg-tertiary',
  awaiting_session: 'text-cyan border-cyan/30 bg-cyan/10',
  creating_session: 'text-cyan border-cyan/30 bg-cyan/10',
  ready: 'text-success border-success/30 bg-success/10',
  sending: 'text-amber border-amber/30 bg-amber/10',
  error: 'text-error border-error/30 bg-error/10',
};

const runtimeStatusLabel: Record<string, string> = {
  not_provisioned: 'Idle',
  provisioning: 'Provisioning',
  running: 'Running',
  stopped: 'Stopped',
  terminated: 'Terminated',
  failed: 'Unavailable',
};

const runtimeStatusTone: Record<string, string> = {
  not_provisioned: 'text-muted border-border bg-bg-tertiary',
  provisioning: 'text-cyan border-cyan/30 bg-cyan/10',
  running: 'text-success border-success/30 bg-success/10',
  stopped: 'text-amber border-amber/30 bg-amber/10',
  terminated: 'text-muted border-border bg-bg-tertiary',
  failed: 'text-error border-error/30 bg-error/10',
};

export const TopBar: React.FC<TopBarProps> = ({ activeTab, onTabChange }) => {
  const { user, login, isLoading } = useAuth();
  const {
    indexCodebaseEnabled,
    setIndexCodebaseEnabled,
    selectedRepository,
    sessionStatus,
    runtimeStatus,
    runtimeError,
    messages,
    contextCards,
  } = useSessionStore(
    useShallow((state) => ({
      indexCodebaseEnabled: state.indexCodebaseEnabled,
      setIndexCodebaseEnabled: state.setIndexCodebaseEnabled,
      selectedRepository: state.selectedRepository,
      sessionStatus: state.sessionStatus,
      runtimeStatus: state.runtimeStatus,
      runtimeError: state.runtimeError,
      messages: state.messages,
      contextCards: state.contextCards,
    }))
  );

  const handleLoginClick = () => {
    if (!user && !isLoading) {
      login();
    }
  };

  const repositoryLabel = selectedRepository
    ? `${selectedRepository.repository.full_name}@${selectedRepository.branch}`
    : 'No repository selected';

  const statusClass = sessionStatusTone[sessionStatus] || sessionStatusTone.no_repo;
  const statusText = sessionStatusLabel[sessionStatus] || sessionStatus;
  const runtimeClass =
    runtimeStatusTone[runtimeStatus] || runtimeStatusTone.not_provisioned;
  const runtimeText = runtimeStatusLabel[runtimeStatus] || runtimeStatus;

  return (
    <header className="border-b border-border bg-[linear-gradient(110deg,rgba(245,158,11,0.08)_0%,rgba(34,211,238,0.04)_34%,rgba(17,17,19,0.95)_100%)] backdrop-blur-sm">
      <div className="px-4 pt-4 pb-3 flex flex-wrap items-start gap-4 justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-amber/10 border border-amber/30 flex items-center justify-center glow-amber">
            <Bot className="w-5 h-5 text-amber" />
          </div>
          <div className="min-w-0">
            <p className="text-fg font-mono font-semibold text-base truncate">Yudai Chat Workspace</p>
            <p className="text-xs text-fg-secondary font-mono truncate mt-0.5">{repositoryLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          <span
            className={`px-3 py-1.5 rounded-md text-xs font-mono border ${statusClass}`}
            title={`Session status: ${statusText}`}
          >
            Session {statusText}
          </span>

          <span
            className={`px-3 py-1.5 rounded-md text-xs font-mono border ${runtimeClass}`}
            title={runtimeError ? `Runtime status: ${runtimeText}. ${runtimeError}` : `Runtime status: ${runtimeText}`}
          >
            Runtime {runtimeText}
          </span>

          <button
            type="button"
            onClick={() => setIndexCodebaseEnabled(!indexCodebaseEnabled)}
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono border transition-colors
              ${indexCodebaseEnabled
                ? 'bg-cyan/10 text-cyan border-cyan/30 hover:bg-cyan/15'
                : 'bg-bg-tertiary text-fg-secondary border-border hover:text-fg'}
            `}
            aria-pressed={indexCodebaseEnabled}
          >
            <Database className="w-3.5 h-3.5" />
            Indexing
          </button>

          {user ? (
            <UserProfile />
          ) : (
            <button
              onClick={handleLoginClick}
              disabled={isLoading}
              className="flex items-center gap-2 text-fg hover:text-amber bg-bg-tertiary border border-border rounded-md px-3 py-1.5 text-xs font-mono transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Sign in with GitHub"
            >
              <User className="w-4 h-4" />
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          )}
        </div>
      </div>

      <div className="px-4 pb-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/60">
        <div className="flex gap-2 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`
                  flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-mono whitespace-nowrap transition-all
                  ${isActive
                    ? 'bg-amber/10 text-amber border-amber/40 glow-amber'
                    : 'bg-bg-tertiary text-fg-secondary border-border hover:text-fg hover:border-border-accent'}
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-md text-xs font-mono border border-border text-fg-secondary bg-bg-tertiary">
            {messages.length} msg
          </span>
          <span className="px-2.5 py-1 rounded-md text-xs font-mono border border-border text-fg-secondary bg-bg-tertiary">
            {contextCards.length} ctx
          </span>
        </div>
      </div>
    </header>
  );
};
