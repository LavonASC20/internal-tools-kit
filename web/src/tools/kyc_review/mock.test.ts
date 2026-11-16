import { installMock, resetMock } from '../../mock';
import { loginAs } from '../../test/render';

const post = (path: string, body: unknown = {}) =>
  fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

beforeAll(() => installMock());
beforeEach(() => resetMock());

test('/api/me lists the KYC actions the role holds', async () => {
  await loginAs('audrey');
  const me = await (await fetch('/api/me')).json();
  expect(me.actions).toContain('audit.read');
  expect(me.actions.filter((a: string) => a.startsWith('kyc.'))).toEqual(['kyc.case.read']);
});

test('auditor receives masked PII, analyst receives raw values', async () => {
  await loginAs('audrey');
  const masked = await (await fetch('/api/kyc/cases/1')).json();
  expect(masked.national_id).toBe('***');
  expect(masked.date_of_birth).toBe('***');
  await loginAs('ana');
  const raw = await (await fetch('/api/kyc/cases/1')).json();
  expect(raw.national_id).toMatch(/^FAKE-/);
});

test('KYC flow: propose, self-approval refused, approve by another reviewer, audited', async () => {
  await loginAs('dana');
  const proposed = await post('/api/kyc/cases/2/propose', { decision: 'clear', rationale: 'docs verified' });
  expect(proposed.status).toBe(200);
  const req = { id: (await proposed.json()).approval_request_id };
  expect((await (await fetch('/api/kyc/cases/2')).json()).status).toBe('pending_approval');

  const self = await post(`/api/approvals/${req.id}/approve`);
  expect(self.status).toBe(403);
  expect((await self.json()).error.code).toBe('self_approval');

  await loginAs('ana');
  expect((await post(`/api/approvals/${req.id}/approve`)).status).toBe(403);

  await loginAs('sam');
  expect((await post(`/api/approvals/${req.id}/approve`, { comment: 'ok' })).status).toBe(200);
  expect((await (await fetch('/api/kyc/cases/2')).json()).status).toBe('cleared');
  expect((await post(`/api/approvals/${req.id}/approve`)).status).toBe(409);

  expect((await fetch('/api/audit')).status).toBe(403);
  await loginAs('audrey');
  const audit = await (await fetch('/api/audit')).json();
  expect(audit.map((e: { action: string }) => e.action)).toEqual([
    'kyc.decision.apply',
    'approvals.approve',
    'kyc.decision.propose',
  ]);
  expect(JSON.stringify(audit)).not.toContain('FAKE-');
});

test('rejecting a request returns the case to open', async () => {
  await loginAs('ana');
  const { approval_request_id: id } = await (
    await post('/api/kyc/cases/3/propose', { decision: 'reject', rationale: 'r' })
  ).json();
  await loginAs('sam');
  expect((await post(`/api/approvals/${id}/reject`)).status).toBe(200);
  expect((await (await fetch('/api/kyc/cases/3')).json()).status).toBe('open');
  await loginAs('audrey');
  expect((await (await fetch('/api/audit')).json())[0].action).toBe('kyc.decision.return');
});

test('authorization runs before validation', async () => {
  await loginAs('sam');
  const res = await post('/api/kyc/cases/1/propose', { decision: 'nope' });
  expect(res.status).toBe(403);
});
