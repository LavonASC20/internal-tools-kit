import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { installMock, resetMock } from '../../mock';
import { loginAs, renderAt } from '../../test/render';
import { FlagDetailPage } from './FlagDetailPage';

beforeAll(() => installMock());
beforeEach(() => resetMock());

// Mock seed ids: 1-6 dev, 7-12 staging, 13-18 prod.
const renderFlag = (id: number) => renderAt(`/feature_flags/${id}`, '/feature_flags/:flagId', <FlagDetailPage />);

test('engineer sees a direct toggle on a dev flag', async () => {
  await loginAs('eli');
  renderFlag(1);
  expect(await screen.findByRole('button', { name: /in dev$/ })).toBeInTheDocument();
  expect(screen.queryByText('Request a prod toggle')).not.toBeInTheDocument();
});

test('engineer sees a request form, not a toggle, on a prod flag', async () => {
  await loginAs('eli');
  renderFlag(13);
  expect(await screen.findByText('Request a prod toggle')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /in dev$|in staging$/ })).not.toBeInTheDocument();
});

test('submitting a prod request shows it waiting for approval', async () => {
  await loginAs('eli');
  renderFlag(13);
  await userEvent.type(await screen.findByLabelText(/Reason/), 'Launch day');
  await userEvent.click(screen.getByRole('button', { name: /in prod$/ }));
  expect(await screen.findByText('Waiting for approval')).toBeInTheDocument();
});

test('auditor sees the flag but no toggle or request form', async () => {
  await loginAs('audrey');
  renderFlag(13);
  expect(await screen.findByText('demo_new_checkout')).toBeInTheDocument();
  expect(screen.queryByText('Request a prod toggle')).not.toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
