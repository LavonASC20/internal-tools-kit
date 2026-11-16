import { MockHttpError, type MockTool } from '../../mock/types';
import { ENVIRONMENTS, FLAG_READ, FLAG_TOGGLE, PROD_APPROVE, PROD_PROPOSE, type Flag } from './types';

interface State {
  flags: Flag[];
}

const KEYS: [string, string][] = [
  ['demo_new_checkout', 'Fake checkout redesign for the demo'],
  ['demo_dark_mode', 'Fake dark theme toggle'],
  ['demo_search_v2', 'Fake second search backend'],
  ['demo_beta_banner', 'Fake banner for beta testers'],
  ['demo_fast_export', 'Fake faster CSV export'],
  ['demo_sample_widget', 'Fake dashboard widget'],
];

function seedFlags(): Flag[] {
  let id = 0;
  return ENVIRONMENTS.flatMap((environment, e) =>
    KEYS.map(([key, description], k) => ({
      id: ++id,
      key,
      environment,
      description,
      enabled: (k + e) % 3 !== 2 && !(environment === 'prod' && k % 2 === 1),
      pending_request_id: null,
      updated_by: null,
      updated_at: '2026-11-01T00:00:00Z',
    })),
  );
}

function findFlag(state: State, id: string): Flag {
  const f = state.flags.find((x) => String(x.id) === id);
  if (!f) throw new MockHttpError(404, 'not_found', 'Feature flag not found');
  return f;
}

function readEnabled(body: unknown): boolean {
  const enabled = (body as { enabled?: unknown } | null)?.enabled;
  if (typeof enabled !== 'boolean') throw new MockHttpError(422, 'validation_error', 'enabled must be a boolean');
  return enabled;
}

function requireChange(f: Flag, enabled: boolean) {
  if (f.enabled === enabled) {
    throw new MockHttpError(409, 'invalid_state', `Flag ${f.key} is already ${enabled ? 'enabled' : 'disabled'}`);
  }
}

const entity = (f: Flag) => `feature_flag:${f.id}`;
const detail = (f: Flag, enabled: boolean) => ({ key: f.key, environment: f.environment, from: f.enabled, to: enabled });

// Mirrors ProposeProdToggle.reason in backend/tools/feature_flags/schemas.py (counted in code points).
const REASON_MAX = 500;

const flagsMock: MockTool<State> = {
  tool: 'feature_flags',
  permissions: {
    [FLAG_READ]: ['engineer', 'eng_lead', 'auditor'],
    [FLAG_TOGGLE]: ['engineer', 'eng_lead'],
    [PROD_PROPOSE]: ['engineer', 'eng_lead'],
    [PROD_APPROVE]: ['eng_lead'],
  },
  approvalKinds: [{ action: PROD_APPROVE, proposeAction: PROD_PROPOSE }],
  initialState: () => ({ flags: seedFlags() }),
  routes: [
    {
      method: 'GET',
      path: '/api/flags',
      action: FLAG_READ,
      handle: (ctx) => ctx.state.flags,
    },
    {
      method: 'GET',
      path: '/api/flags/:id',
      action: FLAG_READ,
      handle: (ctx, { id }) => findFlag(ctx.state, id),
    },
    {
      method: 'POST',
      path: '/api/flags/:id/toggle',
      action: FLAG_TOGGLE,
      handle: (ctx, { id }, body) => {
        const enabled = readEnabled(body);
        const f = findFlag(ctx.state, id);
        if (f.environment === 'prod') {
          throw new MockHttpError(409, 'invalid_state', 'Prod flags change only through an approved request');
        }
        requireChange(f, enabled);
        ctx.audit({ action: FLAG_TOGGLE, entity: entity(f), detail: detail(f, enabled) });
        Object.assign(f, { enabled, updated_by: ctx.user.id, updated_at: new Date().toISOString() });
        return f;
      },
    },
    {
      method: 'POST',
      path: '/api/flags/:id/propose',
      action: PROD_PROPOSE,
      handle: (ctx, { id }, body) => {
        const enabled = readEnabled(body);
        const reason = (body as { reason?: unknown }).reason;
        if (typeof reason !== 'string' || !reason.trim()) {
          throw new MockHttpError(422, 'validation_error', 'reason is required');
        }
        if ([...reason.trim()].length > REASON_MAX) {
          throw new MockHttpError(422, 'validation_error', `reason is at most ${REASON_MAX} characters`);
        }
        const f = findFlag(ctx.state, id);
        if (f.environment !== 'prod') {
          throw new MockHttpError(409, 'invalid_state', 'Only prod flags need approval; toggle this one directly');
        }
        if (f.pending_request_id !== null) {
          throw new MockHttpError(409, 'invalid_state', `Flag ${f.key} already has a pending request`);
        }
        requireChange(f, enabled);
        const req = ctx.requestApproval({
          action: PROD_APPROVE,
          entity: entity(f),
          payload: { flag_id: f.id, key: f.key, environment: f.environment, enabled, reason: reason.trim() },
        });
        f.pending_request_id = req.id;
        ctx.audit({
          action: PROD_PROPOSE,
          entity: entity(f),
          detail: { ...detail(f, enabled), approval_request_id: req.id },
        });
        return { flag: f, approval_request_id: req.id };
      },
    },
  ],
  onDecision: (ctx, req, outcome) => {
    const f = findFlag(ctx.state, String(req.payload.flag_id));
    if (f.pending_request_id !== req.id) {
      throw new MockHttpError(409, 'invalid_state', 'Flag is not waiting on this request');
    }
    f.pending_request_id = null;
    if (outcome === 'approved') {
      const enabled = Boolean(req.payload.enabled);
      ctx.audit({
        action: 'flags.prod.apply',
        entity: entity(f),
        detail: { ...detail(f, enabled), approval_request_id: req.id },
        authorizedBy: req.action,
      });
      Object.assign(f, { enabled, updated_by: ctx.user.id, updated_at: new Date().toISOString() });
    } else {
      ctx.audit({
        action: 'flags.prod.return',
        entity: entity(f),
        detail: { key: f.key, environment: f.environment, approval_request_id: req.id },
        authorizedBy: req.action,
      });
    }
  },
};

export default flagsMock;
