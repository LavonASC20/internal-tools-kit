import { useCallback, useEffect, useState } from 'react';
import { ApiError, api, toApiError } from './api';

interface State<T> {
  data?: T;
  error?: ApiError;
  loading: boolean;
}

export function useApi<T>(path: string) {
  const [state, setState] = useState<State<T>>({ loading: true });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    api
      .get<T>(path)
      .then((data) => !cancelled && setState({ data, loading: false }))
      .catch((err) => !cancelled && setState({ error: toApiError(err), loading: false }));
    return () => {
      cancelled = true;
    };
  }, [path, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}
