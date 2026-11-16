import { useState } from 'react';
import { Button, Card, Center, Group, Stack, Text, Title } from '@mantine/core';
import { toApiError, type ApiError } from './api';
import { ErrorAlert } from './ErrorAlert';
import { useSession } from './session';
import type { Id } from './types';

export function LoginPage() {
  const { users, login } = useSession();
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState<Id | null>(null);

  const pick = async (id: Id) => {
    setError(null);
    setPending(id);
    try {
      await login(id);
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setPending(null);
    }
  };

  return (
    <Center mih="100vh">
      <Card withBorder w={420} padding="lg">
        <Stack>
          <Title order={3}>Sign in as a seeded user</Title>
          <ErrorAlert error={error} title="Login failed" />
          {users.length === 0 && <Text c="dimmed">No users available.</Text>}
          {users.map((u) => (
            <Button
              key={String(u.id)}
              variant="default"
              justify="space-between"
              loading={pending === u.id}
              onClick={() => pick(u.id)}
              rightSection={<Text size="xs" c="dimmed">{u.roles.join(', ')}</Text>}
            >
              <Group>{u.name}</Group>
            </Button>
          ))}
        </Stack>
      </Card>
    </Center>
  );
}
