import React from 'react';
import { Trash2, FileText, MessageCircle, Upload } from 'lucide-react';
import { ContextCard } from '../types';

interface ContextCardsProps {
  cards: ContextCard[];
  onRemoveCard: (id: string) => void;
  onCreateIssue: () => void;
}

export const ContextCards: React.FC<ContextCardsProps> = ({ 
  cards, 
  onRemoveCard, 
  onCreateIssue 
}) => {
  const getSourceIcon = (source: ContextCard['source']) => {
    switch (source) {
      case 'chat': return MessageCircle;
      case 'file-deps': return FileText;
      case 'upload': return Upload;
    }
  };

  const getTokenHeatColor = (tokens: number) => {
    if (tokens < 3000) return 'from-teal-500 to-teal-500';
    if (tokens < 7000) return 'from-teal-500 to-amber-500';
    return 'from-amber-500 to-red-500';
  };

  const totalTokens = cards.reduce((sum, card) => sum + card.tokens, 0);

  return (
    <div className="h-full flex flex-col">
      {/* Cards List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {cards.length === 0 ? (
          <div className="text-center py-12 text-fg/60">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No context cards yet</p>
            <p className="text-sm">Add items from chat or file dependencies</p>
          </div>
        ) : (
          cards.map((card) => {
            const SourceIcon = getSourceIcon(card.source);
            
            return (
              <div
                key={card.id}
                className="bg-zinc-800/50 rounded-xl p-4 group hover:bg-zinc-800 
                         transition-colors border border-zinc-700/50"
              >
                {/* Token Heat Bar */}
                <div className="h-1 w-full rounded-full bg-zinc-700 mb-3 overflow-hidden">
                  <div 
                    className={`h-full bg-gradient-to-r ${getTokenHeatColor(card.tokens)}`}
                    style={{ width: `${Math.min((card.tokens / 100000) * 100, 100)}%` }}
                  />
                </div>

                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-fg text-sm mb-1 truncate">
                      {card.title}
                    </h3>
                    <p className="text-fg/70 text-sm line-clamp-2 mb-3">
                      {card.description}
                    </p>
                    
                    <div className="flex items-center gap-3">
                      <span className="bg-zinc-800 px-2 py-0.5 rounded-full text-xs text-fg/80">
                        {card.tokens.toLocaleString()} tokens
                      </span>
                      <div className="flex items-center gap-1">
                        <SourceIcon className="w-3 h-3 text-fg/60" />
                        <span className="text-xs uppercase font-mono text-fg/60">
                          {card.source}
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => onRemoveCard(card.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity
                             p-1 hover:bg-error/20 rounded text-error"
                    aria-label="Remove card"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-fg/70">
            {cards.length} cards • {totalTokens.toLocaleString()} total tokens
          </span>
        </div>
        <button
          onClick={onCreateIssue}
          disabled={cards.length === 0}
          className="w-full h-11 bg-primary hover:bg-primary/80 disabled:opacity-50 
                   disabled:cursor-not-allowed text-white rounded-xl font-medium 
                   transition-colors"
        >
          Create GitHub Issue
        </button>
      </div>
    </div>
  );
};