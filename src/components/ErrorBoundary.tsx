import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Wifi, WifiOff } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  isWebSocketError: boolean;
  isAuthError: boolean;
  isNetworkError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    isWebSocketError: false,
    isAuthError: false,
    isNetworkError: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    // Analyze error type
    const isWebSocketError = error.message.includes('WebSocket') || 
                            error.message.includes('connection') ||
                            error.message.includes('realtime');
    
    const isAuthError = error.message.includes('authentication') || 
                       error.message.includes('unauthorized') ||
                       error.message.includes('token');
    
    const isNetworkError = error.message.includes('network') || 
                          error.message.includes('fetch') ||
                          error.message.includes('connection');

    return {
      hasError: true,
      error,
      isWebSocketError,
      isAuthError,
      isNetworkError,
    };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      isWebSocketError: false,
      isAuthError: false,
      isNetworkError: false,
    });
  };

  private handleRefresh = () => {
    window.location.reload();
  };

  private handleReconnect = () => {
    // Trigger WebSocket reconnection by refreshing the page
    // This will cause the SessionContext to reinitialize the connection
    window.location.reload();
  };

  private handleReauth = () => {
    // Clear auth tokens and redirect to login
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    window.location.href = '/login';
  };

  public render() {
    if (this.state.hasError) {
      const { error, isWebSocketError, isAuthError, isNetworkError } = this.state;

      // Custom fallback UI based on error type
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-center mb-4">
              {isWebSocketError ? (
                <WifiOff className="h-12 w-12 text-orange-500" />
              ) : isAuthError ? (
                <AlertTriangle className="h-12 w-12 text-red-500" />
              ) : isNetworkError ? (
                <Wifi className="h-12 w-12 text-blue-500" />
              ) : (
                <AlertTriangle className="h-12 w-12 text-red-500" />
              )}
            </div>

            <h2 className="text-xl font-semibold text-gray-900 text-center mb-2">
              {isWebSocketError && 'Connection Error'}
              {isAuthError && 'Authentication Error'}
              {isNetworkError && 'Network Error'}
              {!isWebSocketError && !isAuthError && !isNetworkError && 'Something went wrong'}
            </h2>

            <p className="text-gray-600 text-center mb-6">
              {isWebSocketError && 'We lost connection to the server. This might be temporary.'}
              {isAuthError && 'Your session has expired. Please log in again.'}
              {isNetworkError && 'Unable to connect to the server. Please check your internet connection.'}
              {!isWebSocketError && !isAuthError && !isNetworkError && 'An unexpected error occurred. Please try again.'}
            </p>

            {error && (
              <details className="mb-4">
                <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                  Error details
                </summary>
                <pre className="mt-2 text-xs text-gray-600 bg-gray-100 p-2 rounded overflow-auto max-h-32">
                  {error.message}
                </pre>
              </details>
            )}

            <div className="space-y-3">
              {isWebSocketError && (
                <button
                  onClick={this.handleReconnect}
                  className="w-full flex items-center justify-center px-4 py-2 bg-orange-500 text-white rounded-md hover:bg-orange-600 transition-colors"
                >
                  <Wifi className="h-4 w-4 mr-2" />
                  Reconnect
                </button>
              )}

              {isAuthError && (
                <button
                  onClick={this.handleReauth}
                  className="w-full flex items-center justify-center px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors"
                >
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Log In Again
                </button>
              )}

              {isNetworkError && (
                <button
                  onClick={this.handleRetry}
                  className="w-full flex items-center justify-center px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
                >
                  <Wifi className="h-4 w-4 mr-2" />
                  Retry Connection
                </button>
              )}

              <button
                onClick={this.handleRetry}
                className="w-full flex items-center justify-center px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Try Again
              </button>

              <button
                onClick={this.handleRefresh}
                className="w-full flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}