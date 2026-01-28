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
    <div className="flex h-14 items-center px-4 border-b border-[#2a2a2e] bg-[#111113] backdrop-blur-sm">
      {/* Logo & Project Switcher */}
      <div className="flex items-center gap-2 mr-8">
        <div className="w-8 h-8 bg-gradient-to-br from-[#f59e0b] to-[#f59e0b]/80 rounded-lg flex items-center justify-center shadow-lg shadow-[#f59e0b]/20">
          <span className="text-[#0a0a0b] font-bold text-sm font-mono">AI</span>
        </div>
        <button className="flex items-center gap-1 text-[#f4f4f5] hover:text-[#f59e0b] transition-colors duration-200 group">
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
                    ? 'bg-[#f59e0b] text-[#0a0a0b] shadow-lg shadow-[#f59e0b]/30 animate-pulse-subtle'
                    : isError
                    ? 'bg-red-500/90 text-white border border-red-400/30'
                    : isCompleted
                    ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/30'
                    : 'bg-[#1a1a1d] text-[#71717a] border border-[#2a2a2e] hover:border-[#3d3d42]'
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
              ? 'bg-[#22d3ee]/15 text-[#22d3ee] border border-[#22d3ee]/30 hover:bg-[#22d3ee]/20 shadow-sm shadow-[#22d3ee]/10'
              : 'bg-[#1a1a1d] text-[#a1a1aa] border border-[#2a2a2e] hover:border-[#3d3d42] hover:text-[#f4f4f5]'
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
            className="flex items-center gap-2 text-[#f4f4f5] hover:text-[#f59e0b] transition-all duration-200 bg-[#1a1a1d] hover:bg-[#1a1a1d]/80 border border-[#2a2a2e] hover:border-[#3d3d42] rounded-md px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed group"
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
