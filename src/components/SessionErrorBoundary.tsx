import React, { Component, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface SessionErrorBoundaryProps {
  children: ReactNode;
  onSessionError?: () => void;
  onRetry?: () => void;
}

interface SessionErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  isSessionError: boolean;
}

/**
 * Error Boundary specifically designed for session-related errors
 * Provides graceful error handling with session recovery options
 */
export class SessionErrorBoundary extends Component<SessionErrorBoundaryProps, SessionErrorBoundaryState> {
  private retryCount = 0;
  private maxRetries = 3;

  constructor(props: SessionErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      isSessionError: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<SessionErrorBoundaryState> {
    // Check if it's a session-related error
    const isSessionError = error.message.includes('Session not found') ||
                          error.message.includes('session') ||
                          error.message.includes('404') ||
                          error.message.includes('Authentication');

    return {
      hasError: true,
      error,
      isSessionError,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[SessionErrorBoundary] Caught error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });

    // If it's a session error, notify parent to handle session cleanup
    if (this.state.isSessionError && this.props.onSessionError) {
      this.props.onSessionError();
    }
  }

  handleRetry = () => {
    if (this.retryCount < this.maxRetries) {
      this.retryCount++;
      console.log(`[SessionErrorBoundary] Retry attempt ${this.retryCount}/${this.maxRetries}`);
      
      this.setState({
        hasError: false,
        error: null,
        errorInfo: null,
        isSessionError: false,
      });

      if (this.props.onRetry) {
        this.props.onRetry();
      }
    }
  };

  handleGoHome = () => {
    // Clear error state and navigate to home
    this.retryCount = 0;
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      isSessionError: false,
    });
    
    // Reload the page to reset the application state
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      const { error, isSessionError } = this.state;
      const canRetry = this.retryCount < this.maxRetries;

      return (
        <div className="min-h-screen bg-bg flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-8 max-w-lg w-full">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-red-600/20 rounded-lg">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">
                  {isSessionError ? 'Session Error' : 'Application Error'}
                </h1>
                <p className="text-zinc-400 text-sm">
                  {isSessionError 
                    ? 'There was a problem with your session' 
                    : 'Something went wrong'
                  }
                </p>
              </div>
            </div>

            <div className="bg-zinc-800 border border-zinc-700 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-medium text-zinc-300 mb-2">Error Details:</h3>
              <p className="text-sm text-zinc-400 font-mono break-all">
                {error?.message || 'Unknown error occurred'}
              </p>
            </div>

            {isSessionError && (
              <div className="bg-blue-600/10 border border-blue-600/20 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-medium text-blue-300 mb-2">Session Recovery</h3>
                <p className="text-sm text-blue-200">
                  Your session may have expired or become invalid. We'll help you get back on track.
                </p>
              </div>
            )}

            <div className="space-y-3">
              {canRetry && (
                <button
                  onClick={this.handleRetry}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  <RefreshCw size={16} />
                  Try Again ({this.maxRetries - this.retryCount} attempts remaining)
                </button>
              )}

              <button
                onClick={this.handleGoHome}
                className="w-full bg-zinc-700 hover:bg-zinc-600 text-white px-4 py-2 rounded-lg flex items-center justify-center gap-2 transition-colors"
              >
                <Home size={16} />
                {isSessionError ? 'Start New Session' : 'Go to Home'}
              </button>
            </div>

            {process.env.NODE_ENV === 'development' && (
              <details className="mt-6">
                <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
                  Technical Details (Development)
                </summary>
                <pre className="text-xs text-zinc-400 mt-2 p-2 bg-zinc-800 rounded border overflow-auto">
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Hook version of SessionErrorBoundary for use with React hooks
 */
export const withSessionErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<SessionErrorBoundaryProps, 'children'>
) => {
  const WrappedComponent = (props: P) => (
    <SessionErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </SessionErrorBoundary>
  );

  WrappedComponent.displayName = `withSessionErrorBoundary(${Component.displayName || Component.name})`;
  
  return WrappedComponent;
};