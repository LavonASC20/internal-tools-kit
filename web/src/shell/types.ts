// Shapes from SPEC section 5. Field names the spec does not pin down are noted.

export type Id = string | number;

export interface User {
  id: Id;
  name: string;
  roles: string[];
}

export interface Me extends User {
  // SPEC: "allowed actions". Assumed field name: `actions`.
  actions: string[];
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface ApprovalRequest {
  id: Id;
  tool: string;
  // The action a decider must hold to approve or reject this request.
  action: string;
  entity: string;
  payload: Record<string, unknown>;
  proposed_by: Id;
  status: ApprovalStatus;
  decided_by?: Id | null;
  comment?: string | null;
  created_at?: string;
  decided_at?: string | null;
  // Set by the backend: pending, not proposed by the caller, and the caller holds `action`.
  // Not used to gate Decide, so a self-approval attempt reaches the server and shows its `self_approval` error.
  can_decide: boolean;
}

export interface AuditEvent {
  id: Id;
  actor: Id;
  role: string;
  tool: string;
  action: string;
  entity: string;
  detail: Record<string, unknown> | null;
  at?: string;
}
