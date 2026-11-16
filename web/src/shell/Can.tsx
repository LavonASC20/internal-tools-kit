import type { ReactNode } from 'react';
import { useSession } from './session';

// Renders children only when GET /api/me lists the action.
export function Can({ action, children }: { action: string; children: ReactNode }) {
  const { can } = useSession();
  return can(action) ? <>{children}</> : null;
}
