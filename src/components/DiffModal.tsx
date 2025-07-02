import React from 'react';
import { X, ExternalLink, GitBranch } from 'lucide-react';

interface DiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  prNumber?: number;
  branchName?: string;
}

export const DiffModal: React.FC<DiffModalProps> = ({
  isOpen,
  onClose,
  prNumber = 123,
  branchName = 'yudai-assistant/feature-update'
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-7xl h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <div className="flex items-center gap-4">
            <GitBranch className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-fg">Pull Request #{prNumber}</h2>
              <p className="text-sm text-fg/60">{branchName}</p>
            </div>
            <span className="bg-success/20 text-success px-2 py-1 rounded text-xs font-medium">
              yudai-assistant
            </span>
          </div>

          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5 text-fg" />
          </button>
        </div>

        {/* Diff Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="grid grid-cols-2 gap-6 h-full">
            {/* Before */}
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <div className="bg-error/10 px-4 py-2 border-b border-zinc-800">
                <span className="text-sm font-medium text-error">Before</span>
              </div>
              <pre className="p-4 text-sm font-mono text-fg bg-zinc-900/50 h-full overflow-auto">
                <code>{`function oldFunction() {
  return 'old logic';
}`}</code>
              </pre>
            </div>

            {/* After */}
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <div className="bg-success/10 px-4 py-2 border-b border-zinc-800">
                <span className="text-sm font-medium text-success">After</span>
              </div>
              <pre className="p-4 text-sm font-mono text-fg bg-zinc-900/50 h-full overflow-auto">
                <code>{`function newFunction() {
  return 'improved logic with better performance';
}

// Added new utility function
function helperFunction() {
  return 'helper utility';
}`}</code>
              </pre>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-zinc-800 flex justify-end">
          <a
            href="#"
            className="flex items-center gap-2 bg-primary hover:bg-primary/80 text-white px-4 py-2 rounded-lg transition-colors"
          >
            Open PR on GitHub
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>
    </div>
  );
};

