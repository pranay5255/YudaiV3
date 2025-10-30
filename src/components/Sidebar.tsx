import React from 'react';
import { MessageCircle, CreditCard, Lightbulb, Route, ChevronLeft, ChevronRight } from 'lucide-react';
import { TabType } from '../types';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

const tabs = [
  { id: 'chat' as TabType, label: 'Chat', icon: MessageCircle },
  { id: 'context' as TabType, label: 'Context for Issue', icon: CreditCard },
  { id: 'trajectories' as TabType, label: 'Trajectories', icon: Route },
  { id: 'ideas' as TabType, label: 'Ideas to Implement', icon: Lightbulb },
];

export const Sidebar: React.FC<SidebarProps> = ({ 
  activeTab, 
  onTabChange, 
  isCollapsed, 
  onToggleCollapse 
}) => {
  return (
    <div className={`
      h-screen sticky top-0 bg-bg/95 backdrop-blur border-r border-zinc-800 
      transition-all duration-240 ease-out
      ${isCollapsed ? 'w-16' : 'w-64'}
    `}>
      {/* Collapse Toggle */}
      <div className="flex justify-end p-2 border-b border-zinc-800">
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4 text-fg" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-fg" />
          )}
        </button>
      </div>

      {/* Tabs */}
      <nav className="p-2">
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
                  ? 'bg-primary/10 text-primary border-l-2 border-primary' 
                  : 'text-fg/70 hover:text-fg hover:bg-zinc-800/50'
                }
                ${isCollapsed ? 'justify-center' : 'justify-start'}
              `}
              title={isCollapsed ? tab.label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!isCollapsed && (
                <span className="font-medium text-sm truncate">{tab.label}</span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
};
