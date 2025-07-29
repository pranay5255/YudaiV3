import { beforeAll, afterEach, afterAll } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// Global test setup
beforeAll(() => {
  // Setup any global configurations
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  // Mock window.matchMedia
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => {},
    }),
  });

  // Mock fetch for API tests
  global.fetch = fetch;
});

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Global cleanup
afterAll(() => {
  // Clean up any global state
});

// Mock environment variables for testing
process.env.VITE_API_URL = 'https://yudai.app/api';
process.env.NODE_ENV = 'test'; 