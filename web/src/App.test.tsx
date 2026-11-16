import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';
import { installMock, resetMock } from './mock';
import { SessionProvider } from './shell/session';
import { loginAs } from './test/render';

beforeAll(() => installMock());
beforeEach(() => resetMock());

test('switching user refetches the page instead of showing the previous user data', async () => {
  await loginAs('ana');
  render(
    <MantineProvider>
      <MemoryRouter initialEntries={['/kyc_review/1']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <SessionProvider>
          <App />
        </SessionProvider>
      </MemoryRouter>
    </MantineProvider>,
  );
  expect(await screen.findByText('FAKE-000-0001')).toBeInTheDocument();

  await userEvent.click(screen.getByRole('textbox', { name: 'Switch user' }));
  await userEvent.click(await screen.findByRole('option', { name: 'Audrey' }));

  expect(await screen.findAllByText('***')).toHaveLength(2);
  expect(screen.queryByText('FAKE-000-0001')).not.toBeInTheDocument();
});
