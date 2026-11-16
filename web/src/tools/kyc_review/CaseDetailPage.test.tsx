import { screen } from '@testing-library/react';
import { installMock, resetMock } from '../../mock';
import { loginAs, renderAt } from '../../test/render';
import { CaseDetailPage } from './CaseDetailPage';

beforeAll(() => installMock());
beforeEach(() => resetMock());

const renderCase = () => renderAt('/kyc_review/1', '/kyc_review/:caseId', <CaseDetailPage />);

test('propose form is shown when /api/me lists kyc.decision.propose', async () => {
  await loginAs('ana');
  renderCase();
  expect(await screen.findByText('Propose a decision')).toBeInTheDocument();
});

test('propose form is hidden when /api/me does not list kyc.decision.propose', async () => {
  await loginAs('sam');
  renderCase();
  expect(await screen.findByText('Case 1')).toBeInTheDocument();
  expect(screen.queryByText('Propose a decision')).not.toBeInTheDocument();
});

test('auditor sees masked PII as returned by the API', async () => {
  await loginAs('audrey');
  renderCase();
  expect(await screen.findByText('Case 1')).toBeInTheDocument();
  expect(screen.getAllByText('***')).toHaveLength(2);
});
