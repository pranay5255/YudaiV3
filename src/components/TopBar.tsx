import React from 'react';
import { useShallow } from 'zustand/react/shallow';
import { ChevronDown, Database, User } from 'lucide-react';
import { ProgressStep } from '../types';
import { UserProfile } from './UserProfile';
import { useAuth } from '../hooks/useAuth';
import { useSessionStore } from '../stores/sessionStore';

interface TopBarProps {
  currentStep: ProgressStep;
  errorStep?: ProgressStep;
}

const steps: ProgressStep[] = ['DAifu', 'Architect', 'Test-Writer', 'Coder'];

export const TopBar: React.FC<TopBarProps> = ({ currentStep, errorStep }) => {
  const { user, login, isLoading } = useAuth();
  const { indexCodebaseEnabled, setIndexCodebaseEnabled } = useSessionStore(
    useShallow((state) => ({
      indexCodebaseEnabled: state.indexCodebaseEnabled,
      setIndexCodebaseEnabled: state.setIndexCodebaseEnabled,
    }))
  );

  const handleLoginClick = () => {
    if (!user && !isLoading) {
      login();
    }
  };

  return (
    <div className="flex h-14 items-center px-4 border-b border-border bg-bg-secondary backdrop-blur-sm">
      {/* Logo & Project Switcher */}
      <div className="flex items-center gap-2 mr-8">
        <div className="w-8 h-8 bg-gradient-to-br from-accent-amber to-accent-amber/80 rounded-lg flex items-center justify-center shadow-lg shadow-accent-amber/20">
          <span className="text-bg-primary font-bold text-sm font-mono">AI</span>
        </div>
        <button className="flex items-center gap-1 text-text-primary hover:text-accent-amber transition-colors duration-200 group">
          <span className="font-medium text-sm">Project Assistant</span>
          <ChevronDown className="w-4 h-4 group-hover:translate-y-0.5 transition-transform duration-200" />
        </button>
      </div>

      {/* Progress Stepper */}
      <div className="flex items-center gap-3 flex-1">
        <div className="flex items-center gap-2">
          {steps.map((step, index) => {
            const isActive = step === currentStep;
            const isError = step === errorStep;
            const isCompleted = steps.indexOf(currentStep) > index;

            return (
              <div
                key={step}
                className={`
                  relative px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all duration-300
                  ${isActive
                    ? 'bg-accent-amber text-bg-primary shadow-lg shadow-accent-amber/30 animate-pulse-subtle'
                    : isError
                    ? 'bg-red-500/90 text-white border border-red-400/30'
                    : isCompleted
                    ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30'
                    : 'bg-bg-tertiary text-text-muted border border-border hover:border-border-accent'
                  }
                `}
                role="status"
                aria-current={isActive ? 'step' : undefined}
              >
                {step}
              </div>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => setIndexCodebaseEnabled(!indexCodebaseEnabled)}
          className={`
            relative flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all duration-200
            ${indexCodebaseEnabled
              ? 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30 hover:bg-accent-cyan/20 shadow-sm shadow-accent-cyan/10'
              : 'bg-bg-tertiary text-text-secondary border border-border hover:border-border-accent hover:text-text-primary'
            }
          `}
          aria-pressed={indexCodebaseEnabled}
        >
          <Database className={`w-3.5 h-3.5 transition-transform duration-200 ${indexCodebaseEnabled ? 'scale-110' : ''}`} />
          Index codebase
        </button>
      </div>

      {/* Right Side Controls */}
      <div className="flex items-center gap-3">
        {user ? (
          // Show full UserProfile component when logged in
          <UserProfile />
        ) : (
          // Show login button when not logged in
          <button
            onClick={handleLoginClick}
            disabled={isLoading}
            className="flex items-center gap-2 text-text-primary hover:text-accent-amber transition-all duration-200 bg-bg-tertiary hover:bg-bg-tertiary/80 border border-border hover:border-border-accent rounded-md px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed group"
            aria-label="Sign in with GitHub"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                <span className="text-xs font-medium font-mono">Signing in...</span>
              </>
            ) : (
              <>
                <User className="w-4 h-4 group-hover:scale-110 transition-transform duration-200" />
                <span className="text-xs font-medium font-mono">Sign in</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
