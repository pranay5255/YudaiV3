/**
 * Session Error Handling Test Utilities
 * 
 * These utilities can be used to test the session error handling in development
 * by simulating various error scenarios that could occur in production.
 */

// Test scenarios for session error handling
export const SessionErrorTests = {
  /**
   * Simulate a session not found error (404)
   * This tests the automatic session clearing mechanism
   */
  simulateSessionNotFound: () => {
    console.log('🧪 [SessionTest] Simulating session not found error');
    
    // Create a mock 404 error similar to what the API would return
    const mockError = new Error('Session not found');
    console.error('[ApiService] Parsed error data:', { detail: 'Session not found' });
    console.error('[ApiService] Throwing error: Session not found');
    
    return mockError;
  },

  /**
   * Simulate network connectivity issues
   * This tests the retry mechanism with exponential backoff
   */
  simulateNetworkError: () => {
    console.log('🧪 [SessionTest] Simulating network error');
    
    const mockError = new Error('Network request failed');
    console.error('[ApiService] Network error occurred');
    
    return mockError;
  },

  /**
   * Simulate authentication token expiry
   * This tests the auth error handling
   */
  simulateAuthError: () => {
    console.log('🧪 [SessionTest] Simulating auth error');
    
    const mockError = new Error('HTTP error! status: 401');
    console.error('[ApiService] 401 Unauthorized, redirecting to login');
    
    return mockError;
  },

  /**
   * Test session validation with invalid session ID
   * This tests the session store validation mechanism
   */
  testInvalidSessionId: () => {
    console.log('🧪 [SessionTest] Testing invalid session ID validation');
    
    // This would be the type of session ID that's causing the production issue
    const invalidSessionId = 'session_8c2041a12825';
    console.log(`Testing validation for session: ${invalidSessionId}`);
    
    return invalidSessionId;
  },

  /**
   * Log current session state for debugging
   */
  logSessionState: () => {
    console.log('🧪 [SessionTest] Current session state check:');
    
    // Check localStorage
    const sessionToken = localStorage.getItem('session_token');
    console.log('- Session token in localStorage:', sessionToken ? 'Found' : 'Not found');
    
    // Check if there's persisted Zustand state
    const persistedState = localStorage.getItem('session-storage');
    if (persistedState) {
      try {
        const parsed = JSON.parse(persistedState);
        console.log('- Persisted session state:', {
          activeSessionId: parsed.state?.activeSessionId,
          isAuthenticated: parsed.state?.isAuthenticated,
          sessionInitialized: parsed.state?.sessionInitialized,
          selectedRepository: !!parsed.state?.selectedRepository
        });
      } catch {
        console.log('- Could not parse persisted state');
      }
    } else {
      console.log('- No persisted session state found');
    }
  },

  /**
   * Clear all session-related storage (useful for testing fresh state)
   */
  clearAllSessionData: () => {
    console.log('🧪 [SessionTest] Clearing all session data');
    
    localStorage.removeItem('session_token');
    localStorage.removeItem('session-storage');
    
    console.log('- All session data cleared');
  }
};

/**
 * Development helper to test session error scenarios
 * Usage in browser console: 
 * 
 * import { testSessionErrors } from './utils/sessionErrorTest';
 * testSessionErrors.logState();
 */
export const testSessionErrors = {
  // Log current state
  logState: SessionErrorTests.logSessionState,
  
  // Clear session data for testing
  clearData: SessionErrorTests.clearAllSessionData,
  
  // Test invalid session scenario (like production issue)
  testInvalidSession: () => {
    SessionErrorTests.logSessionState();
    const invalidId = SessionErrorTests.testInvalidSessionId();
    console.log(`🧪 This session ID (${invalidId}) should be automatically cleared by the new error handling`);
  }
};

// Export for use in components during development
export default SessionErrorTests;