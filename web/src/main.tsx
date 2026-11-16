import '@mantine/core/styles.css';
import { MantineProvider } from '@mantine/core';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { SessionProvider } from './shell/session';

async function start() {
  if (import.meta.env.VITE_USE_MOCK === 'true') {
    const { installMock } = await import('./mock');
    installMock();
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <MantineProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <SessionProvider>
            <App />
          </SessionProvider>
        </BrowserRouter>
      </MantineProvider>
    </StrictMode>,
  );
}

start();
