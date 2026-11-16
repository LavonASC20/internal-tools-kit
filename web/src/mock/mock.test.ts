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
  for (const user of ['audrey', 'eli']) {
    await loginAs(user);
    expect((await fetch('/api/approvals')).status).toBe(403);
  }
});

test('audit requires audit.read', async () => {
  await loginAs('ana');
  expect((await fetch('/api/audit')).status).toBe(403);
});
