// Contract for per-tool mock handlers (web/src/tools/<name>/mock.ts).
// The mock stands in for the backend while it is built; it is the only place in web/
// that makes policy decisions, mirroring what the backend does.

import type { ApprovalRequest } from '../shell/types';

export interface MockUser {
  id: string;
  name: string;
  roles: string[];
}

export class MockHttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export interface MockContext<S> {
  user: MockUser;
  state: S;
  can: (action: string) => boolean;
  audit: (event: { action: string; entity: string; detail?: Record<string, unknown> }) => void;
  requestApproval: (req: { action: string; entity: string; payload: Record<string, unknown> }) => ApprovalRequest;
  mask: <T extends object>(obj: T, fields: (keyof T)[], piiAction: string) => T;
}

export interface MockRoute<S> {
  method: 'GET' | 'POST';
  // Express-style path, e.g. /api/kyc/cases/:id
  path: string;
  action: string;
  handle: (ctx: MockContext<S>, params: Record<string, string>, body: unknown) => unknown;
}

export interface MockTool<S> {
  tool: string;
  // action -> roles that hold it
  permissions: Record<string, string[]>;
  initialState: () => S;
  routes: MockRoute<S>[];
  onDecision: (ctx: MockContext<S>, req: ApprovalRequest, outcome: 'approved' | 'rejected') => void;
}
