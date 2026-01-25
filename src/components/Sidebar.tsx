import React from 'react';
import { MessageCircle, CreditCard, FileText, ChevronLeft, ChevronRight, Zap } from 'lucide-react';
import { TabType } from '../types';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

const tabs = [
  { id: 'chat' as TabType, label: 'Chat', icon: MessageCircle, color: 'amber' },
  { id: 'context' as TabType, label: 'Context for Issue', icon: CreditCard, color: 'cyan' },
  { id: 'ideas' as TabType, label: 'Trajectory Viewer', icon: FileText, color: 'success' },
  { id: 'solve' as TabType, label: 'Solve Issues', icon: Zap, color: 'amber' },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse
}) => {
  return (
    <div className={`
      h-screen sticky top-0 bg-bg-secondary backdrop-blur-sm border-r border-border
      transition-all duration-200 ease-out terminal-noise
      ${isCollapsed ? 'w-16' : 'w-64'}
    `}>
      {/* Logo/Brand */}
      <div className="p-4 border-b border-border">
        <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 rounded-lg bg-amber/10 border border-amber/20 flex items-center justify-center glow-amber">
            <span className="text-amber font-mono font-bold text-sm">Y3</span>
          </div>
          {!isCollapsed && (
            <div className="animate-fade-in">
              <span className="font-mono font-semibold text-fg text-sm">YudaiV3</span>
              <span className="block text-xs text-muted font-mono">context-engineered</span>
            </div>
          )}
        </div>
      </div>

      {/* Collapse Toggle */}
      <div className="flex justify-end p-2 border-b border-border/50">
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:bg-bg-tertiary text-muted hover:text-fg transition-all duration-200 group"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          ) : (
            <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          )}
        </button>
      </div>

      {/* Navigation Tabs */}
      <nav className="p-2 space-y-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                w-full flex items-center gap-3 p-3 rounded-lg transition-all duration-200
                ${isActive
                  ? 'bg-amber/10 text-amber border-l-2 border-amber'
                  : 'text-fg-secondary hover:text-fg hover:bg-bg-tertiary border-l-2 border-transparent'
                }
                ${isCollapsed ? 'justify-center' : 'justify-start'}
              `}
              title={isCollapsed ? tab.label : undefined}
              style={isActive ? { boxShadow: '0 0 15px rgba(245, 158, 11, 0.08)' } : undefined}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-amber' : ''}`} />
              {!isCollapsed && (
                <span className="font-mono text-sm truncate">{tab.label}</span>
              )}
              {isActive && !isCollapsed && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-amber animate-pulse" style={{ boxShadow: '0 0 6px rgba(245, 158, 11, 0.5)' }} />
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Section */}
      {!isCollapsed && (
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border/50 animate-fade-in">
          <div className="text-xs text-muted font-mono space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" style={{ boxShadow: '0 0 6px rgba(16, 185, 129, 0.5)' }} />
              <span>System Active</span>
            </div>
            <p className="text-fg-muted/50">v3.0.0 terminal-precision</p>
          </div>
        </div>
      )}
    </div>
  );
};
