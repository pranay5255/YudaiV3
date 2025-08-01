import React from 'react';
import { X, FileText, Plus } from 'lucide-react';
import { FileItem } from '../types/fileDependencies';

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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-fg">{file.file_name}</h2>
              <p className="text-sm text-fg/60">
                {file.file_type} • {file.tokens} tokens
              </p>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5 text-fg" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <div className="bg-zinc-800 px-4 py-2 border-b border-zinc-700">
              <span className="text-sm font-medium text-fg">File Contents</span>
            </div>
            <pre className="p-4 text-sm font-mono text-fg overflow-auto max-h-96">
              <code>{mockContent}</code>
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-zinc-800 flex justify-end">
          <button
            onClick={() => {
              onAddToContext(file);
              onClose();
            }}
            className="flex items-center gap-2 bg-primary hover:bg-primary/80 
                     text-white px-4 py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add to Context
          </button>
        </div>
      </div>
    </div>
  );
};