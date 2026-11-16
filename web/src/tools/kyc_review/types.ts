import type { Id } from '../../shell/types';

export type CaseStatus = 'open' | 'pending_approval' | 'cleared' | 'rejected';

// SPEC section 6. national_id and date_of_birth arrive masked unless the caller holds kyc.pii.read.
export interface KycCase {
  id: Id;
  subject_name: string;
  national_id: string;
  date_of_birth: string;
  risk_flag: string;
  status: CaseStatus;
}

export const statusColor: Record<CaseStatus, string> = {
  open: 'blue',
  pending_approval: 'yellow',
  cleared: 'green',
  rejected: 'red',
};
