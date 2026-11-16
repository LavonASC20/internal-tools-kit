import { Alert } from '@mantine/core';
import type { ApiError } from './api';

export function ErrorAlert({ error, title = 'Error' }: { error?: ApiError | null; title?: string }) {
  if (!error) return null;
  return (
    <Alert color="red" title={title}>
      {error.message} ({error.code})
    </Alert>
  );
}
