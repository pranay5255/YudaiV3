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

// Updated to match the database schema from models.py
export interface FileItem {
  id: string;
  name: string; // file/directory name
  path?: string; // full path (optional for frontend)
  type: 'INTERNAL' | 'EXTERNAL'; // matches FileType enum from models.py
  tokens: number; // int
  Category: string; // category classification
  isDirectory: boolean; // matches is_directory from database
  children?: FileItem[];
  expanded?: boolean; // frontend-only state
  content?: string; // optional file content
  content_size?: number; // optional content size
}

// API response type for the filedeps endpoint
export interface FileItemAPIResponse {
  id?: string;
  name?: string;
  path?: string;
  type?: string; // can be any string from API
  tokens?: number;
  category?: string;
  Category?: string;
  isDirectory?: boolean;
  children?: FileItemAPIResponse[];
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

