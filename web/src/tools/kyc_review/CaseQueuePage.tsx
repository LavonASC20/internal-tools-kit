import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Anchor, Badge, Group, SegmentedControl, Stack, Table, Text, Title } from '@mantine/core';
import { asList } from '../../shell/api';
import { ErrorAlert } from '../../shell/ErrorAlert';
import { useApi } from '../../shell/useApi';
import { statusColor, type KycCase } from './types';

export function CaseQueuePage() {
  const { data, error, loading } = useApi<unknown>('/api/kyc/cases');
  const [filter, setFilter] = useState('open');

  const cases = asList<KycCase>(data).filter((c) => filter === 'all' || c.status === filter);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>KYC case queue</Title>
        <SegmentedControl
          value={filter}
          onChange={setFilter}
          data={[
            { value: 'open', label: 'Open' },
            { value: 'pending_approval', label: 'Pending approval' },
            { value: 'cleared', label: 'Cleared' },
            { value: 'rejected', label: 'Rejected' },
            { value: 'all', label: 'All' },
          ]}
        />
      </Group>
      <ErrorAlert error={error} />
      {!loading && !error && cases.length === 0 && <Text c="dimmed">No cases.</Text>}
      {cases.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Subject</Table.Th>
              <Table.Th>Risk flag</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {cases.map((c) => (
              <Table.Tr key={String(c.id)}>
                <Table.Td>{c.id}</Table.Td>
                <Table.Td>
                  <Anchor component={Link} to={String(c.id)}>
                    {c.subject_name}
                  </Anchor>
                </Table.Td>
                <Table.Td>{c.risk_flag}</Table.Td>
                <Table.Td>
                  <Badge color={statusColor[c.status]}>{c.status}</Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
