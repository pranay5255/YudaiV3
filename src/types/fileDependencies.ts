/**
 * File Dependencies Types
 * 
 * These types are used for the file dependency tree component and are separate
 * from the UnifiedSessionState. File dependencies are managed by the backend
 * filedeps service and don't need to be part of real-time session state.
 */

export interface FileItem {
  id: string;
  file_name: string;
  file_path: string;
  file_type: string;
  content_summary?: string;
  tokens: number;
  created_at: string;
  children?: FileItem[];
  expanded?: boolean;
}

export interface DbFileItem {
  id: number;
  name: string;
  path: string;
  file_type: 'INTERNAL' | 'EXTERNAL';
  category: string;
  tokens: number;
  is_directory: boolean;
  created_at?: string;
  parent_id?: number;
}