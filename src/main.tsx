import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { AuthProvider } from './contexts/AuthContext.tsx';
import { RepositoryProvider } from './contexts/RepositoryContext.tsx';
import { SessionProvider } from './contexts/SessionContext.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <RepositoryProvider>
        <SessionProvider>
          <App />
        </SessionProvider>
      </RepositoryProvider>
    </AuthProvider>
  </StrictMode>
);
