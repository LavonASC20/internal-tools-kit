import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Anchor, Badge, Group, SegmentedControl, Stack, Table, Text, Title } from '@mantine/core';
import { asList } from '../../shell/api';
import { ErrorAlert } from '../../shell/ErrorAlert';
import { useSession } from '../../shell/session';
import { useApi } from '../../shell/useApi';
import { EnabledBadge } from './EnabledBadge';
import { envColor, type Flag } from './types';

export function FlagListPage() {
  const { userName } = useSession();
  const { data, error, loading } = useApi<unknown>('/api/flags');
  const [filter, setFilter] = useState('all');

  const flags = asList<Flag>(data).filter((f) => filter === 'all' || f.environment === filter);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Feature flags</Title>
        <SegmentedControl
          value={filter}
          onChange={setFilter}
          data={[
            { value: 'all', label: 'All' },
            { value: 'dev', label: 'Dev' },
            { value: 'staging', label: 'Staging' },
            { value: 'prod', label: 'Prod' },
          ]}
        />
      </Group>
      <ErrorAlert error={error} />
      {!loading && !error && flags.length === 0 && <Text c="dimmed">No flags.</Text>}
      {flags.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Flag</Table.Th>
              <Table.Th>Environment</Table.Th>
              <Table.Th>State</Table.Th>
              <Table.Th>Last changed by</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {flags.map((f) => (
              <Table.Tr key={String(f.id)}>
                <Table.Td>
                  <Anchor component={Link} to={String(f.id)}>
                    {f.key}
                  </Anchor>
                  <Text size="xs" c="dimmed">
                    {f.description}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={envColor[f.environment]}>
                    {f.environment}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <EnabledBadge enabled={f.enabled} />
                    {f.pending_request_id !== null && <Badge color="yellow">pending approval</Badge>}
                  </Group>
                </Table.Td>
                <Table.Td>{userName(f.updated_by)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
