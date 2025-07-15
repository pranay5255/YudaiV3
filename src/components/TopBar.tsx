import React from 'react';
import { ChevronDown, Moon, Github } from 'lucide-react';
import { ProgressStep } from '../types';

interface TopBarProps {
  currentStep: ProgressStep;
  errorStep?: ProgressStep;
}

const steps: ProgressStep[] = ['DAifu', 'Architect', 'Test-Writer', 'Coder'];

export const TopBar: React.FC<TopBarProps> = ({ currentStep, errorStep }) => {
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

      {/* Right Side Controls */}
      <div className="flex items-center gap-3">
        <button 
          className="p-2 rounded-lg hover:bg-zinc-800 transition-colors"
          aria-label="Toggle theme"
        >
          <Moon className="w-5 h-5 text-fg" />
        </button>
        <div className="w-8 h-8 bg-zinc-800 rounded-full flex items-center justify-center">
          <Github className="w-4 h-4 text-fg" />
        </div>
      </div>
    </div>
  );
};