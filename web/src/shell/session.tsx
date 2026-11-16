import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, api, asList, setUnauthorizedHandler } from './api';
import type { Id, Me, User } from './types';

interface Session {
  me: Me | null;
  users: User[];
  loading: boolean;
  login: (userId: Id) => Promise<void>;
  // True only when GET /api/me lists the action. The frontend never derives permissions itself.
  can: (action: string) => boolean;
  userName: (id: Id | null | undefined) => string;
}

const SessionContext = createContext<Session | null>(null);

function normalizeMe(raw: Me & { allowed_actions?: string[] }): Me {
  return { ...raw, roles: raw.roles ?? [], actions: raw.actions ?? raw.allowed_actions ?? [] };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      setMe(normalizeMe(await api.get<Me>('/api/me')));
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) console.error(err);
      setMe(null);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setMe(null));
    Promise.all([
      api.get<unknown>('/api/users').then((d) => setUsers(asList<User>(d))).catch(() => setUsers([])),
      loadMe(),
    ]).finally(() => setLoading(false));
    return () => setUnauthorizedHandler(null);
  }, [loadMe]);

  const login = useCallback(
    async (userId: Id) => {
      await api.post('/api/auth/login', { user_id: userId });
      await loadMe();
    },
    [loadMe],
  );

  const value = useMemo<Session>(() => {
    const actions = new Set(me?.actions ?? []);
    const names = new Map(users.map((u) => [String(u.id), u.name]));
    return {
      me,
      users,
      loading,
      login,
      can: (action) => actions.has(action),
      userName: (id) => (id === null || id === undefined ? '' : names.get(String(id)) ?? String(id)),
    };
  }, [me, users, loading, login]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
