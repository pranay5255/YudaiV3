import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { AuthProvider } from './contexts/AuthProvider';
import { RepositoryProvider } from './contexts/RepositoryProvider';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <RepositoryProvider>
        <App />
      </RepositoryProvider>
    </AuthProvider>
  </StrictMode>
);
