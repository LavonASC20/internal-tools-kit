import { installMock, resetMock } from '.';
import type { MockTool } from './types';
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

const toolMocks = import.meta.glob<{ default: MockTool<unknown> }>('../tools/*/mock.ts', { eager: true });
const approvalActions = Object.values(toolMocks).flatMap((m) =>
  m.default.approvalKinds.flatMap((k) => [k.action, k.proposeAction]),
);

test('approvals list requires approvals.read', async () => {
  let outsider: string | undefined;
  for (const user of ['ana', 'sam', 'dana', 'audrey', 'eli', 'lee']) {
    await loginAs(user);
    const { actions } = await (await fetch('/api/me')).json();
    if (!actions.some((a: string) => approvalActions.includes(a))) {
      outsider = user;
      break;
    }
  }
  expect(outsider).toBeDefined();
  await loginAs(outsider!);
  expect((await fetch('/api/approvals')).status).toBe(403);
});

test('audit requires audit.read', async () => {
  await loginAs('ana');
  expect((await fetch('/api/audit')).status).toBe(403);
});
