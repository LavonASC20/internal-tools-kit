// In-browser mock of the backend routes in SPEC sections 5 and 6.
// Enabled with VITE_USE_MOCK=true (npm run dev:mock). Never bundled otherwise.

import type { ApprovalRequest, AuditEvent } from '../shell/types';
import { MockHttpError, type MockContext, type MockTool, type MockUser } from './types';

const USERS: MockUser[] = [
  { id: 'ana', name: 'Ana', roles: ['analyst'] },
  { id: 'sam', name: 'Sam', roles: ['senior_reviewer'] },
  { id: 'dana', name: 'Dana', roles: ['analyst', 'senior_reviewer'] },
  { id: 'audrey', name: 'Audrey', roles: ['auditor'] },
  { id: 'eli', name: 'Eli', roles: ['engineer'] },
  { id: 'lee', name: 'Lee', roles: ['engineer', 'eng_lead'] },
];

const CORE_PERMISSIONS: Record<string, string[]> = { 'audit.read': ['auditor'] };

const STORAGE_KEY = 'itk-mock-db-v2';
const SESSION_KEY = 'itk-mock-user';

type AnyTool = MockTool<any>;

const toolModules = import.meta.glob<{ default: AnyTool }>('../tools/*/mock.ts', { eager: true });
const mockTools: AnyTool[] = Object.values(toolModules).map((m) => m.default);

interface Db {
  approvals: ApprovalRequest[];
  audit: AuditEvent[];
  tools: Record<string, unknown>;
  nextId: number;
}

function freshDb(): Db {
  return {
    approvals: [],
    audit: [],
    tools: Object.fromEntries(mockTools.map((t) => [t.tool, t.initialState()])),
    nextId: 1,
  };
}

let db: Db = freshDb();

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) db = { ...freshDb(), ...JSON.parse(raw) };
  } catch {
    db = freshDb();
  }
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    // storage unavailable
  }
}

export function resetMock() {
  db = freshDb();
  try {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // storage unavailable
  }
}

function declaredRolesFor(action: string): string[] {
  const all = [CORE_PERMISSIONS, ...mockTools.map((t) => t.permissions)];
  return all.flatMap((p) => p[action] ?? []);
}

// Mirrors core.approvals: approvals.read = proposers and deciders of any kind, approvals.decide = deciders.
function derivedRolesFor(action: string): string[] {
  const kinds = mockTools.flatMap((t) => t.approvalKinds);
  if (action === 'approvals.read') {
    return kinds.flatMap((k) => [...declaredRolesFor(k.action), ...declaredRolesFor(k.proposeAction)]);
  }
  if (action === 'approvals.decide') return kinds.flatMap((k) => declaredRolesFor(k.action));
  return [];
}

function rolesFor(action: string): string[] {
  return [...declaredRolesFor(action), ...derivedRolesFor(action)];
}

function allActions(): string[] {
  const declared = [CORE_PERMISSIONS, ...mockTools.map((t) => t.permissions)].flatMap(Object.keys);
  return Array.from(new Set([...declared, 'approvals.read', 'approvals.decide']));
}

function grantingRoles(user: MockUser, action: string): string[] {
  const granted = user.roles.filter((r) => rolesFor(action).includes(r));
  return (granted.length ? granted : user.roles).slice().sort();
}

function canDecide(user: MockUser, req: ApprovalRequest): boolean {
  return req.status === 'pending' && req.proposed_by !== user.id && userCan(user, req.action);
}

function approvalOut(user: MockUser, req: ApprovalRequest): ApprovalRequest {
  return { ...req, can_decide: canDecide(user, req) };
}

function meOut(user: MockUser) {
  return { ...user, roles: user.roles.slice().sort(), actions: allActions().filter((a) => userCan(user, a)).sort() };
}

function userCan(user: MockUser, action: string) {
  return rolesFor(action).some((r) => user.roles.includes(r));
}

function currentUser(): MockUser | null {
  const id = sessionStorage.getItem(SESSION_KEY);
  return USERS.find((u) => u.id === id) ?? null;
}

function contextFor<S>(user: MockUser, tool: string): MockContext<S> {
  return {
    user,
    state: db.tools[tool] as S,
    can: (action) => userCan(user, action),
    audit: ({ action, entity, detail, authorizedBy }) => {
      db.audit.unshift({
        id: db.nextId++,
        at: new Date().toISOString(),
        actor: user.id,
        role: grantingRoles(user, authorizedBy ?? action).join(','),
        tool,
        action,
        entity,
        detail: detail ?? {},
      });
    },
    requestApproval: ({ action, entity, payload }) => {
      const req: ApprovalRequest = {
        id: db.nextId++,
        tool,
        action,
        entity,
        payload,
        proposed_by: user.id,
        status: 'pending',
        decided_by: null,
        comment: null,
        created_at: new Date().toISOString(),
        decided_at: null,
        can_decide: false,
      };
      db.approvals.unshift(req);
      return req;
    },
    mask: (obj, fields, piiAction) => {
      if (userCan(user, piiAction)) return obj;
      const copy = { ...obj };
      for (const f of fields) (copy as Record<string, unknown>)[f as string] = '***';
      return copy;
    },
  };
}

function matchPath(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split('/');
  const a = path.split('/');
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

function requireUser(): MockUser {
  const user = currentUser();
  if (!user) throw new MockHttpError(401, 'unauthenticated', 'Not signed in');
  return user;
}

function requireAction(user: MockUser, action: string) {
  if (!userCan(user, action)) throw new MockHttpError(403, 'forbidden', `Missing action ${action}`);
}

function decide(id: string, outcome: 'approved' | 'rejected', body: unknown) {
  const user = requireUser();
  requireAction(user, 'approvals.decide');
  const req = db.approvals.find((r) => String(r.id) === id);
  if (!req) throw new MockHttpError(404, 'not_found', 'Approval request not found');
  requireAction(user, req.action);
  if (req.proposed_by === user.id) {
    throw new MockHttpError(403, 'self_approval', 'You cannot decide your own request');
  }
  if (req.status !== 'pending') throw new MockHttpError(409, 'invalid_state', 'Request is not pending');
  const tool = mockTools.find((t) => t.tool === req.tool);
  const ctx = contextFor(user, req.tool);
  req.status = outcome;
  req.decided_by = user.id;
  req.comment = (body as { comment?: string } | null)?.comment ?? null;
  req.decided_at = new Date().toISOString();
  ctx.audit({
    action: outcome === 'approved' ? 'approvals.approve' : 'approvals.reject',
    entity: req.entity,
    detail: { approval_request_id: req.id, request_action: req.action },
    authorizedBy: req.action,
  });
  tool?.onDecision(ctx, req, outcome);
  return approvalOut(user, req);
}

function route(method: string, path: string, body: unknown): unknown {
  if (method === 'GET' && path === '/api/users') return USERS;
  if (method === 'POST' && path === '/api/auth/login') {
    const user = USERS.find((u) => u.id === String((body as { user_id?: unknown })?.user_id));
    if (!user) throw new MockHttpError(401, 'unauthenticated', 'Unknown user');
    sessionStorage.setItem(SESSION_KEY, user.id);
    return meOut(user);
  }
  if (method === 'GET' && path === '/api/me') return meOut(requireUser());
  if (method === 'GET' && path === '/api/approvals') {
    const user = requireUser();
    requireAction(user, 'approvals.read');
    const visible = mockTools
      .flatMap((t) => t.approvalKinds)
      .filter((k) => userCan(user, k.action) || userCan(user, k.proposeAction))
      .map((k) => k.action);
    return db.approvals.filter((r) => visible.includes(r.action)).map((r) => approvalOut(user, r));
  }
  if (method === 'GET' && path === '/api/audit') {
    requireAction(requireUser(), 'audit.read');
    return db.audit;
  }
  if (method === 'POST') {
    const m = path.match(/^\/api\/approvals\/([^/]+)\/(approve|reject)$/);
    if (m) return decide(m[1], m[2] === 'approve' ? 'approved' : 'rejected', body);
  }
  for (const tool of mockTools) {
    for (const r of tool.routes) {
      if (r.method !== method) continue;
      const params = matchPath(r.path, path);
      if (!params) continue;
      const user = requireUser();
      requireAction(user, r.action);
      return r.handle(contextFor(user, tool.tool), params, body);
    }
  }
  throw new MockHttpError(404, 'not_found', `No mock route for ${method} ${path}`);
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

export function installMock() {
  load();
  const realFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(href, globalThis.location?.origin ?? 'http://localhost');
    if (!url.pathname.startsWith('/api/')) return realFetch(input, init);
    const method = (init?.method ?? 'GET').toUpperCase();
    let body: unknown = null;
    if (typeof init?.body === 'string') {
      try {
        body = JSON.parse(init.body);
      } catch {
        return json(422, { error: { code: 'validation_error', message: 'Invalid JSON' } });
      }
    }
    try {
      const snapshot = JSON.stringify(db);
      try {
        const result = route(method, url.pathname, body);
        save();
        return json(200, result ?? {});
      } catch (err) {
        db = JSON.parse(snapshot);
        throw err;
      }
    } catch (err) {
      if (err instanceof MockHttpError) {
        return json(err.status, { error: { code: err.code, message: err.message } });
      }
      return json(500, { error: { code: 'internal', message: String(err) } });
    }
  };
}
