import React, { useState } from 'react';
import { ChevronRight, ChevronDown, Plus, Folder, File } from 'lucide-react';
import { FileItem } from '../types';

interface FileDependenciesProps {
  onAddToContext: (file: FileItem) => void;
  onShowDetails: (file: FileItem) => void;
}

const sampleFiles: FileItem[] = [
  {
    id: '1',
    name: 'src',
    type: 'internal',
    tokens: 0,
    isDirectory: true,
    expanded: true,
    children: [
      { id: '2', name: 'components', type: 'internal', tokens: 0, isDirectory: true, children: [
        { id: '3', name: 'Button.tsx', type: 'internal', tokens: 245 },
        { id: '4', name: 'Modal.tsx', type: 'internal', tokens: 892 },
      ]},
      { id: '5', name: 'utils', type: 'internal', tokens: 0, isDirectory: true, children: [
        { id: '6', name: 'helpers.ts', type: 'internal', tokens: 156 },
      ]},
      { id: '7', name: 'App.tsx', type: 'internal', tokens: 423 },
    ],
  },
  {
    id: '8',
    name: 'Libraries / Frameworks',
    type: 'external',
    tokens: 0,
    isDirectory: true,
    expanded: false,
    children: [
      { id: '9', name: 'react', type: 'external', tokens: 15420 },
      { id: '10', name: 'typescript', type: 'external', tokens: 8934 },
      { id: '11', name: 'tailwindcss', type: 'external', tokens: 3245 },
    ],
  },
];

export const FileDependencies: React.FC<FileDependenciesProps> = ({ 
  onAddToContext, 
  onShowDetails 
}) => {
  const [files, setFiles] = useState<FileItem[]>(sampleFiles);

  const toggleExpanded = (id: string) => {
    const updateFiles = (items: FileItem[]): FileItem[] => {
      return items.map(item => {
        if (item.id === id) {
          return { ...item, expanded: !item.expanded };
        }
        if (item.children) {
          return { ...item, children: updateFiles(item.children) };
        }
        return item;
      });
    };
    setFiles(updateFiles(files));
  };

  const getTokenBadgeColor = (tokens: number) => {
    if (tokens === 0) return 'bg-zinc-700 text-fg/60';
    if (tokens < 1000) return 'bg-success/20 text-success';
    if (tokens < 5000) return 'bg-amber/20 text-amber';
    return 'bg-error/20 text-error';
  };

  const renderFileTree = (items: FileItem[], depth = 0) => {
    return items.map((item) => (
      <React.Fragment key={item.id}>
        <tr 
          className="hover:bg-zinc-800/50 transition-colors cursor-pointer group"
          onClick={() => item.isDirectory ? toggleExpanded(item.id) : onShowDetails(item)}
        >
          <td className="px-4 py-3">
            <div className="flex items-center gap-2" style={{ marginLeft: `${depth * 1.5}rem` }}>
              {item.isDirectory ? (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpanded(item.id);
                    }}
                    className="p-0.5 hover:bg-zinc-700 rounded transition-transform"
                  >
                    {item.expanded ? (
                      <ChevronDown className="w-4 h-4 text-fg" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-fg" />
                    )}
                  </button>
                  <Folder className="w-4 h-4 text-accent" />
                </>
              ) : (
                <>
                  <div className="w-5" />
                  <File className="w-4 h-4 text-fg/60" />
                </>
              )}
              <span className="text-sm text-fg">{item.name}</span>
            </div>
          </td>
          <td className="px-4 py-3">
            <span className={`
              px-2 py-0.5 rounded text-xs font-medium
              ${item.type === 'internal' 
                ? 'bg-primary/20 text-primary' 
                : 'bg-zinc-700 text-fg/80'
              }
            `}>
              {item.type}
            </span>
          </td>
          <td className="px-4 py-3">
            {item.tokens > 0 && (
              <span className={`
                px-2 py-0.5 rounded-full text-xs font-medium
                ${getTokenBadgeColor(item.tokens)}
              `}>
                {item.tokens.toLocaleString()}
              </span>
            )}
          </td>
          <td className="px-4 py-3">
            {!item.isDirectory && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAddToContext(item);
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity
                         p-1 hover:bg-primary/20 rounded text-primary"
                aria-label="Add to context"
              >
                <Plus className="w-4 h-4" />
              </button>
            )}
          </td>
        </tr>
        {item.isDirectory && item.expanded && item.children && (
          renderFileTree(item.children, depth + 1)
        )}
      </React.Fragment>
    ));
  };

  return (
    <div className="h-full overflow-auto">
      <table className="w-full">
        <thead className="border-b border-zinc-800 sticky top-0 bg-bg">
          <tr>
            <th className="text-left px-4 py-3 text-sm font-medium text-fg">Name</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-fg">Type</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-fg">Tokens</th>
            <th className="text-left px-4 py-3 text-sm font-medium text-fg"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800 text-sm">
          {renderFileTree(files)}
        </tbody>
      </table>
    </div>
  );
};