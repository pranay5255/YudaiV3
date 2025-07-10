export interface ContextCard {
  id: string;
  title: string;
  description: string;
  tokens: number;
  source: 'chat' | 'file-deps' | 'upload';
}

export interface IdeaItem {
  id: string;
  title: string;
  complexity: 'S' | 'M' | 'L' | 'XL';
  tests: number;
  confidence: number;
}

export interface FileItem {
  id: string;
  name: string; // path of directory/file
  type: 'INTERNAL' | 'EXTERNAL'; // string (INTERNAL || EXTERNAL)
  tokens: number; // int
  Category: string; // category classification
  isDirectory?: boolean;
  children?: FileItem[];
  expanded?: boolean;
}

export interface Message {
  id: string;
  content: string;
  isCode: boolean;
  timestamp: Date;
}

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

export type ProgressStep = 'PM' | 'Architect' | 'Test-Writer' | 'Coder';
export type TabType = 'chat' | 'file-deps' | 'context' | 'ideas';

