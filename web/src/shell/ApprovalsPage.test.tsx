import { screen } from '@testing-library/react';
import { installMock, resetMock } from '../mock';
import { loginAs, renderAt } from '../test/render';
import { ApprovalsPage } from './ApprovalsPage';

beforeAll(() => installMock());
beforeEach(async () => {
  resetMock();
  await loginAs('ana');
  await fetch('/api/kyc/cases/1/propose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision: 'clear', rationale: 'ok' }),
  });
});

test('Decide is shown when /api/me lists the request action', async () => {
  await loginAs('sam');
  renderAt('/approvals', '/approvals', <ApprovalsPage />);
  expect(await screen.findByRole('button', { name: 'Decide' })).toBeInTheDocument();
});

test('Decide is hidden on a request the backend says the caller cannot decide', async () => {
  await loginAs('dana');
  await fetch('/api/kyc/cases/2/propose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision: 'clear', rationale: 'ok' }),
  });
  renderAt('/approvals', '/approvals', <ApprovalsPage />);
  expect(await screen.findByText('kyc_case:2')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Decide' })).toHaveLength(1);
});

test('Decide is hidden when /api/me does not list the request action', async () => {
  renderAt('/approvals', '/approvals', <ApprovalsPage />);
  expect(await screen.findByText('kyc_case:1')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
});
