import React from 'react';
import { ChevronDown, User, Hash } from 'lucide-react';
import { ProgressStep } from '../types';
import { UserProfile } from './UserProfile';
import { useAuth } from '../contexts/AuthContext';
import { useSession } from '../contexts/SessionContext';

interface TopBarProps {
  currentStep: ProgressStep;
  errorStep?: ProgressStep;
}

const steps: ProgressStep[] = ['DAifu', 'Architect', 'Test-Writer', 'Coder'];

export const TopBar: React.FC<TopBarProps> = ({ currentStep, errorStep }) => {
  const { user, login, isLoading } = useAuth();
  const { currentSessionId } = useSession();

  const handleLoginClick = () => {
    if (!user && !isLoading) {
      login();
    }
  };

  return (
    <div className="flex h-14 items-center px-4 border-b border-zinc-800 bg-bg">
      {/* Logo & Project Switcher */}
      <div className="flex items-center gap-2 mr-8">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">AI</span>
        </div>
        <button className="flex items-center gap-1 text-fg hover:text-primary transition-colors">
          <span className="font-medium">Project Assistant</span>
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>

      {/* Progress Stepper */}
      <div className="flex items-center gap-2 flex-1">
        {steps.map((step, index) => {
          const isActive = step === currentStep;
          const isError = step === errorStep;
          const isCompleted = steps.indexOf(currentStep) > index;
          
          return (
            <div
              key={step}
              className={`
                px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-240
                ${isActive 
                  ? 'bg-primary text-white animate-pulse-subtle' 
                  : isError
                  ? 'bg-error text-white'
                  : isCompleted
                  ? 'bg-success/20 text-success'
                  : 'bg-zinc-800 text-fg/60'
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

      {/* Session ID Display */}
      {currentSessionId && (
        <div className="flex items-center gap-2 mr-4 px-3 py-1.5 bg-zinc-800/50 rounded-lg">
          <Hash className="w-4 h-4 text-primary" />
          <span className="text-xs text-fg/70 font-mono">
            {currentSessionId.substring(0, 8)}...
          </span>
        </div>
      )}

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
            className="flex items-center space-x-2 text-fg hover:text-primary transition-colors duration-200 bg-zinc-800/50 hover:bg-zinc-800 rounded-lg px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Sign in with GitHub"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                <span className="text-sm font-medium">Signing in...</span>
              </>
            ) : (
              <>
                <User className="w-5 h-5" />
                <span className="text-sm font-medium">Sign in</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};