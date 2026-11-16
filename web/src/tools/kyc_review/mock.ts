import { MockHttpError, type MockTool } from '../../mock/types';
import type { KycCase } from './types';

interface State {
  cases: KycCase[];
}

const FIRST = ['Alex', 'Blair', 'Casey', 'Drew', 'Emery', 'Finley', 'Gray', 'Harper', 'Indy', 'Jules'];
const LAST = ['Example', 'Sample', 'Testcase'];
const FLAGS = ['pep', 'sanctions_hit', 'adverse_media', 'high_risk_country'];

function seedCases(): KycCase[] {
  return Array.from({ length: 20 }, (_, i) => {
    const n = i + 1;
    return {
      id: n,
      subject_name: `${FIRST[i % FIRST.length]} ${LAST[i % LAST.length]}`,
      national_id: `FAKE-000-${String(n).padStart(4, '0')}`,
      date_of_birth: `19${70 + (i % 30)}-0${(i % 9) + 1}-1${i % 10}`,
      risk_flag: FLAGS[i % FLAGS.length],
      status: 'open',
    };
  });
}

const PII: (keyof KycCase)[] = ['national_id', 'date_of_birth'];

function findCase(state: State, id: string): KycCase {
  const c = state.cases.find((k) => String(k.id) === id);
  if (!c) throw new MockHttpError(404, 'not_found', 'Case not found');
  return c;
}

const kycMock: MockTool<State> = {
  tool: 'kyc_review',
  permissions: {
    'kyc.case.read': ['analyst', 'senior_reviewer', 'auditor'],
    'kyc.pii.read': ['analyst', 'senior_reviewer'],
    'kyc.decision.propose': ['analyst'],
    'kyc.decision.approve': ['senior_reviewer'],
  },
  initialState: () => ({ cases: seedCases() }),
  routes: [
    {
      method: 'GET',
      path: '/api/kyc/cases',
      action: 'kyc.case.read',
      handle: (ctx) => ctx.state.cases.map((c) => ctx.mask(c, PII, 'kyc.pii.read')),
    },
    {
      method: 'GET',
      path: '/api/kyc/cases/:id',
      action: 'kyc.case.read',
      handle: (ctx, { id }) => ctx.mask(findCase(ctx.state, id), PII, 'kyc.pii.read'),
    },
    {
      method: 'POST',
      path: '/api/kyc/cases/:id/propose',
      action: 'kyc.decision.propose',
      handle: (ctx, { id }, body) => {
        const { decision, rationale } = (body ?? {}) as { decision?: string; rationale?: string };
        if ((decision !== 'clear' && decision !== 'reject') || !rationale?.trim()) {
          throw new MockHttpError(422, 'validation_error', 'decision must be clear or reject, rationale required');
        }
        const c = findCase(ctx.state, id);
        if (c.status !== 'open') throw new MockHttpError(409, 'invalid_state', 'Case is not open');
        c.status = 'pending_approval';
        const req = ctx.requestApproval({
          action: 'kyc.decision.approve',
          entity: `kyc_case:${c.id}`,
          payload: { case_id: c.id, decision, rationale },
        });
        ctx.audit({
          action: 'kyc.decision.propose',
          entity: `kyc_case:${c.id}`,
          detail: { decision, approval_id: req.id },
        });
        return req;
      },
    },
  ],
  onDecision: (ctx, req, outcome) => {
    const c = findCase(ctx.state, String(req.payload.case_id));
    if (outcome === 'approved') c.status = req.payload.decision === 'clear' ? 'cleared' : 'rejected';
    else c.status = 'open';
  },
};

export default kycMock;
