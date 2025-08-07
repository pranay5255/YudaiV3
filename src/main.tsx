import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { AuthProvider } from './contexts/AuthProvider';
import { SessionProvider } from './contexts/SessionProvider';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <SessionProvider>
        <App />
      </SessionProvider>
    </AuthProvider>
  </StrictMode>
);
