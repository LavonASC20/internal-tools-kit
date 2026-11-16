import { MantineProvider } from '@mantine/core';
import { render } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SessionProvider } from '../shell/session';

export async function loginAs(userId: string) {
  await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
}

export function renderAt(path: string, routePath: string, element: ReactNode) {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <SessionProvider>
          <Routes>
            <Route path={routePath} element={element} />
          </Routes>
        </SessionProvider>
      </MemoryRouter>
    </MantineProvider>,
  );
}
