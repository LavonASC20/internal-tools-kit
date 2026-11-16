import type { Id } from '../../shell/types';

export type Environment = 'dev' | 'staging' | 'prod';

export const ENVIRONMENTS: Environment[] = ['dev', 'staging', 'prod'];

export const FLAG_READ = 'flags.flag.read';
export const FLAG_TOGGLE = 'flags.flag.toggle';
export const PROD_PROPOSE = 'flags.prod.propose';
export const PROD_APPROVE = 'flags.prod.approve';

// One row per flag per environment. No PII.
export interface Flag {
  id: Id;
  key: string;
  environment: Environment;
  description: string;
  enabled: boolean;
  // Set while a prod toggle waits for approval.
  pending_request_id: Id | null;
  updated_by: Id | null;
  updated_at: string;
}

export interface ProdProposal {
  flag: Flag;
  approval_request_id: Id;
}

export const envColor: Record<Environment, string> = { dev: 'gray', staging: 'blue', prod: 'red' };
