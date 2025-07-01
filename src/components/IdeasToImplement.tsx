import React, { useState } from 'react';
import { Lightbulb, RefreshCw, ExternalLink } from 'lucide-react';
import { IdeaItem } from '../types';

interface IdeasToImplementProps {
  onCreateIssue: (idea: IdeaItem) => void;
}

const sampleIdeas: IdeaItem[] = [
  {
    id: '1',
    title: 'Implement dark mode toggle with system preference detection',
    complexity: 'M',
    tests: 3,
    confidence: 85,
  },
  {
    id: '2',
    title: 'Add keyboard shortcuts for common actions',
    complexity: 'S',
    tests: 2,
    confidence: 92,
  },
  {
    id: '3',
    title: 'Create advanced file search with fuzzy matching',
    complexity: 'L',
    tests: 5,
    confidence: 78,
  },
];

export const IdeasToImplement: React.FC<IdeasToImplementProps> = ({ onCreateIssue }) => {
  const [ideas, setIdeas] = useState<IdeaItem[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const generateIdeas = async () => {
    setIsGenerating(true);
    // Simulate API call
    setTimeout(() => {
      setIdeas(sampleIdeas);
      setIsGenerating(false);
    }, 1500);
  };

  const getComplexityColor = (complexity: IdeaItem['complexity']) => {
    switch (complexity) {
      case 'S': return 'bg-success/20 text-success';
      case 'M': return 'bg-amber/20 text-amber';
      case 'L': return 'bg-error/20 text-error';
      case 'XL': return 'bg-red-500/20 text-red-400';
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800">
        <button
          onClick={generateIdeas}
          disabled={isGenerating}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 
                   disabled:opacity-50 text-fg rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} />
          Generate Ideas
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {ideas.length === 0 ? (
          <div className="text-center py-12 text-fg/60">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-zinc-800 
                          rounded-full mb-4">
              <Lightbulb className="w-8 h-8" />
            </div>
            <p className="text-lg mb-2">No ideas generated yet</p>
            <p className="text-sm">Click "Generate Ideas" to get AI-powered suggestions</p>
          </div>
        ) : (
          <div className="space-y-3">
            {ideas.map((idea) => (
              <div
                key={idea.id}
                className="bg-zinc-800/50 rounded-xl p-4 hover:bg-zinc-800 
                         transition-colors border border-zinc-700/50"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-fg text-sm mb-3 leading-6">
                      {idea.title}
                    </h3>
                    
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`
                        px-2 py-0.5 rounded text-xs font-medium
                        ${getComplexityColor(idea.complexity)}
                      `}>
                        Cplx {idea.complexity}
                      </span>
                      <span className="bg-zinc-800 text-fg/80 px-2 py-0.5 rounded text-xs">
                        {idea.tests} Tests
                      </span>
                      <span className="bg-zinc-800 text-fg/80 px-2 py-0.5 rounded text-xs">
                        Conf {idea.confidence}%
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => onCreateIssue(idea)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs text-primary 
                             hover:bg-primary/10 rounded border border-primary/30 
                             hover:border-primary/50 transition-colors whitespace-nowrap"
                  >
                    Create Issue
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};