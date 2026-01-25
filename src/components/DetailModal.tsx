import React from 'react';
import { X, FileText, Plus } from 'lucide-react';
import { FileItem } from '../types';

interface DetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  file: FileItem | null;
  onAddToContext: (file: FileItem) => void;
}

export const DetailModal: React.FC<DetailModalProps> = ({
  isOpen,
  onClose,
  file,
  onAddToContext
}) => {
  if (!isOpen || !file) return null;

  const mockContent = `// Sample file content for ${file.file_name}
import React from 'react';
import { useState, useEffect } from 'react';

interface Props {
  title: string;
  description?: string;
}

export const Component: React.FC<Props> = ({ title, description }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  return (
    <div className="component">
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
  );
};`;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg-secondary border border-border rounded-xl shadow-terminal w-full max-w-2xl max-h-[80vh] flex flex-col animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber/10 border border-amber/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-amber" />
            </div>
            <div>
              <h2 className="text-lg font-mono font-semibold text-fg">{file.file_name}</h2>
              <p className="text-xs font-mono text-muted">
                {file.file_type} &bull; {file.tokens} tokens
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors text-muted hover:text-fg"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="bg-bg-tertiary border border-border rounded-xl overflow-hidden">
            <div className="bg-bg-secondary px-4 py-2.5 border-b border-border flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber" />
              <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">File Contents</span>
            </div>
            <pre className="p-4 text-sm font-mono text-fg-secondary overflow-auto max-h-96 leading-relaxed">
              <code>{mockContent}</code>
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border flex justify-end">
          <button
            onClick={() => {
              onAddToContext(file);
              onClose();
            }}
            className="flex items-center gap-2 bg-amber hover:bg-amber/90 text-bg-primary px-5 py-2.5 rounded-lg font-mono text-sm font-semibold transition-all duration-200 glow-amber"
          >
            <Plus className="w-4 h-4" />
            Add to Context
          </button>
        </div>
      </div>
    </div>
  );
};
