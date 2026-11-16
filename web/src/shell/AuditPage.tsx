import { useState } from 'react';
import { Group, Select, Stack, Table, Text, Title } from '@mantine/core';
import { asList } from './api';
import { ErrorAlert } from './ErrorAlert';
import { JsonView } from './JsonView';
import { useSession } from './session';
import type { AuditEvent } from './types';
import { useApi } from './useApi';

export function AuditPage() {
  const { userName } = useSession();
  const { data, error, loading } = useApi<unknown>('/api/audit');
  const [tool, setTool] = useState<string | null>(null);

  const events = asList<AuditEvent>(data);
  const toolNames = Array.from(new Set(events.map((e) => e.tool))).sort();
  const shown = tool ? events.filter((e) => e.tool === tool) : events;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Audit trail</Title>
        <Select placeholder="All tools" clearable value={tool} onChange={setTool} data={toolNames} w={200} />
      </Group>
      <ErrorAlert error={error} />
      {!loading && !error && shown.length === 0 && <Text c="dimmed">No events.</Text>}
      {shown.length > 0 && (
        <Table striped verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Time</Table.Th>
              <Table.Th>Actor</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Tool</Table.Th>
              <Table.Th>Action</Table.Th>
              <Table.Th>Entity</Table.Th>
              <Table.Th>Detail</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {shown.map((e) => (
              <Table.Tr key={String(e.id)}>
                <Table.Td>{e.at ? new Date(e.at).toLocaleString() : ''}</Table.Td>
                <Table.Td>{userName(e.actor)}</Table.Td>
                <Table.Td>{e.role}</Table.Td>
                <Table.Td>{e.tool}</Table.Td>
                <Table.Td>{e.action}</Table.Td>
                <Table.Td>{e.entity}</Table.Td>
                <Table.Td>
                  <JsonView value={e.detail} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
