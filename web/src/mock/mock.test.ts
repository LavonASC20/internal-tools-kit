import { installMock, resetMock } from '.';
import { loginAs } from '../test/render';

beforeAll(() => installMock());
beforeEach(() => resetMock());

test('unauthenticated /api/me is 401', async () => {
  expect((await fetch('/api/me')).status).toBe(401);
});

test('/api/me lists only the actions the role holds', async () => {
  await loginAs('audrey');
  expect((await (await fetch('/api/me')).json()).actions).toContain('audit.read');
  await loginAs('ana');
  expect((await (await fetch('/api/me')).json()).actions).not.toContain('audit.read');
});

test('approvals list requires approvals.read', async () => {
  let denied = 0;
  for (const user of ['ana', 'sam', 'dana', 'audrey', 'eli', 'lee']) {
    await loginAs(user);
    const { actions } = await (await fetch('/api/me')).json();
    const allowed = actions.includes('approvals.read');
    expect((await fetch('/api/approvals')).status).toBe(allowed ? 200 : 403);
    if (!allowed) denied++;
  }
  expect(denied).toBeGreaterThan(0);
});

test('audit requires audit.read', async () => {
  await loginAs('ana');
  expect((await fetch('/api/audit')).status).toBe(403);
});
