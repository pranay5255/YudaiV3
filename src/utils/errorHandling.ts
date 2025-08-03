// TODO: CREATE - Standardized error handling
export enum ErrorType {
  AUTHENTICATION = 'authentication',
  SESSION = 'session',
  NETWORK = 'network',
  VALIDATION = 'validation',
  UNKNOWN = 'unknown'
}

export interface AppError {
  type: ErrorType;
  message: string;
  code?: string;
  details?: unknown;
}

export const handleApiError = (error: unknown): AppError => {
  if (error instanceof Error) {
    if (error.message.includes('Authentication')) {
      return { type: ErrorType.AUTHENTICATION, message: 'Please log in to continue' };
    }
    if (error.message.includes('session')) {
      return { type: ErrorType.SESSION, message: 'Please select a repository to start a session' };
    }
    return { type: ErrorType.UNKNOWN, message: error.message };
  }
  return { type: ErrorType.UNKNOWN, message: 'An unexpected error occurred' };
}; 