import { installMock, resetMock } from '../../mock';
import { loginAs } from '../../test/render';
import type { Flag } from './types';

const post = (path: string, body: unknown = {}) =>
  fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

const flags = async (): Promise<Flag[]> => (await fetch('/api/flags')).json();
const flag = async (key: string, env: string) => (await flags()).find((f) => f.key === key && f.environment === env)!;

beforeAll(() => installMock());
beforeEach(() => resetMock());

test('/api/me lists the flag actions each role holds', async () => {
  const actionsOf = async (user: string) => {
    await loginAs(user);
    return ((await (await fetch('/api/me')).json()).actions as string[]).filter((a) => a.startsWith('flags.'));
  };
  expect(await actionsOf('audrey')).toEqual(['flags.flag.read']);
  expect(await actionsOf('eli')).toEqual(['flags.flag.read', 'flags.flag.toggle', 'flags.prod.propose']);
  expect(await actionsOf('lee')).toEqual([
    'flags.flag.read',
    'flags.flag.toggle',
    'flags.prod.approve',
    'flags.prod.propose',
  ]);
});

test('six flags per environment; auditor can view but not toggle', async () => {
  await loginAs('audrey');
  const all = await flags();
  for (const env of ['dev', 'staging', 'prod']) expect(all.filter((f) => f.environment === env)).toHaveLength(6);
  const dev = all.find((f) => f.environment === 'dev')!;
  expect((await post(`/api/flags/${dev.id}/toggle`, { enabled: !dev.enabled })).status).toBe(403);
});

test('engineer toggles dev directly, prod is refused, and the toggle is audited', async () => {
  await loginAs('eli');
  const dev = await flag('demo_dark_mode', 'dev');
  const res = await post(`/api/flags/${dev.id}/toggle`, { enabled: !dev.enabled });
  expect(res.status).toBe(200);
  expect((await res.json()).enabled).toBe(!dev.enabled);
  const prod = await flag('demo_dark_mode', 'prod');
  expect((await post(`/api/flags/${prod.id}/toggle`, { enabled: !prod.enabled })).status).toBe(409);

  await loginAs('audrey');
  const audit = await (await fetch('/api/audit')).json();
  expect(audit.map((e: { action: string; actor: string }) => [e.actor, e.action])).toEqual([
    ['eli', 'flags.flag.toggle'],
  ]);
});

test('prod toggle: Eli asks, Lee cannot approve his own, Lee approves Eli’s, audited', async () => {
  await loginAs('lee');
  const own = await flag('demo_fast_export', 'prod');
  const ownReq = (await (await post(`/api/flags/${own.id}/propose`, { enabled: !own.enabled, reason: 'r' })).json())
    .approval_request_id;
  const self = await post(`/api/approvals/${ownReq}/approve`);
  expect(self.status).toBe(403);
  expect((await self.json()).error.code).toBe('self_approval');

  await loginAs('eli');
  const prod = await flag('demo_beta_banner', 'prod');
  const proposed = await post(`/api/flags/${prod.id}/propose`, { enabled: !prod.enabled, reason: 'launch' });
  expect(proposed.status).toBe(200);
  const reqId = (await proposed.json()).approval_request_id;
  expect((await flag('demo_beta_banner', 'prod')).enabled).toBe(prod.enabled);
  expect((await post(`/api/approvals/${reqId}/approve`)).status).toBe(403);

  await loginAs('lee');
  expect((await post(`/api/approvals/${reqId}/approve`, { comment: 'ok' })).status).toBe(200);
  const after = await flag('demo_beta_banner', 'prod');
  expect(after.enabled).toBe(!prod.enabled);
  expect(after.pending_request_id).toBeNull();

  await loginAs('audrey');
  const trail = (await (await fetch('/api/audit')).json())
    .filter((e: { entity: string }) => e.entity === `feature_flag:${prod.id}`)
    .map((e: { action: string }) => e.action);
  expect(trail).toEqual(['flags.prod.apply', 'approvals.approve', 'flags.prod.propose']);
});

test('rejecting a prod request leaves the flag unchanged and releases it', async () => {
  await loginAs('eli');
  const prod = await flag('demo_sample_widget', 'prod');
  const { approval_request_id: id } = await (
    await post(`/api/flags/${prod.id}/propose`, { enabled: !prod.enabled, reason: 'r' })
  ).json();
  expect((await post(`/api/flags/${prod.id}/propose`, { enabled: !prod.enabled, reason: 'r' })).status).toBe(409);
  await loginAs('lee');
  expect((await post(`/api/approvals/${id}/reject`)).status).toBe(200);
  expect(await flag('demo_sample_widget', 'prod')).toEqual(prod);
});

test('a prod request needs a reason of at most 500 characters, as the backend', async () => {
  await loginAs('eli');
  const prod = await flag('demo_sample_widget', 'prod');
  for (const reason of ['  ', 'x'.repeat(501)]) {
    expect((await post(`/api/flags/${prod.id}/propose`, { enabled: !prod.enabled, reason })).status).toBe(422);
  }
  expect((await post(`/api/flags/${prod.id}/propose`, { enabled: !prod.enabled, reason: '🚀'.repeat(500) })).status).toBe(200);
});
