import { useState } from 'react';
import { Badge, Button, Group, Modal, SegmentedControl, Stack, Table, Text, Textarea, Title } from '@mantine/core';
import { api, asList, toApiError, type ApiError } from './api';
import { ErrorAlert } from './ErrorAlert';
import { JsonView } from './JsonView';
import { useSession } from './session';
import type { ApprovalRequest, ApprovalStatus } from './types';
import { useApi } from './useApi';

const statusColor: Record<ApprovalStatus, string> = { pending: 'yellow', approved: 'green', rejected: 'red' };

export function ApprovalsPage() {
  const { can, userName } = useSession();
  const { data, error, loading, reload } = useApi<unknown>('/api/approvals');
  const [filter, setFilter] = useState<string>('pending');
  const [deciding, setDeciding] = useState<ApprovalRequest | null>(null);

  const requests = asList<ApprovalRequest>(data).filter((r) => filter === 'all' || r.status === filter);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={3}>Approvals</Title>
        <SegmentedControl
          value={filter}
          onChange={setFilter}
          data={[
            { value: 'pending', label: 'Pending' },
            { value: 'approved', label: 'Approved' },
            { value: 'rejected', label: 'Rejected' },
            { value: 'all', label: 'All' },
          ]}
        />
      </Group>
      <ErrorAlert error={error} />
      {!loading && !error && requests.length === 0 && <Text c="dimmed">No requests.</Text>}
      {requests.length > 0 && (
        <Table striped verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Tool</Table.Th>
              <Table.Th>Entity</Table.Th>
              <Table.Th>Payload</Table.Th>
              <Table.Th>Proposed by</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Decided by</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {requests.map((r) => (
              <Table.Tr key={String(r.id)}>
                <Table.Td>{r.id}</Table.Td>
                <Table.Td>{r.tool}</Table.Td>
                <Table.Td>{r.entity}</Table.Td>
                <Table.Td>
                  <JsonView value={r.payload} />
                </Table.Td>
                <Table.Td>{userName(r.proposed_by)}</Table.Td>
                <Table.Td>
                  <Badge color={statusColor[r.status]}>{r.status}</Badge>
                </Table.Td>
                <Table.Td>
                  {userName(r.decided_by)}
                  {r.comment && (
                    <Text size="xs" c="dimmed">
                      {r.comment}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {r.status === 'pending' && can(r.action) && r.can_decide && (
                    <Button size="xs" onClick={() => setDeciding(r)}>
                      Decide
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <DecideModal
        request={deciding}
        onClose={() => setDeciding(null)}
        onDone={() => {
          setDeciding(null);
          reload();
        }}
      />
    </Stack>
  );
}

function DecideModal({
  request,
  onClose,
  onDone,
}: {
  request: ApprovalRequest | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [comment, setComment] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null);

  const close = () => {
    setComment('');
    setError(null);
    onClose();
  };

  const decide = async (verb: 'approve' | 'reject') => {
    if (!request) return;
    setError(null);
    setSubmitting(verb);
    try {
      await api.post(`/api/approvals/${request.id}/${verb}`, { comment });
      setComment('');
      onDone();
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Modal opened={request !== null} onClose={close} title={`Decide request ${request?.id ?? ''}`}>
      <Stack>
        <Text size="sm">
          {request?.tool} / {request?.entity}
        </Text>
        <JsonView value={request?.payload} />
        <Textarea label="Comment" value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} />
        <ErrorAlert error={error} title="Decision refused" />
        <Group justify="flex-end">
          <Button color="red" variant="light" loading={submitting === 'reject'} onClick={() => decide('reject')}>
            Reject
          </Button>
          <Button color="green" loading={submitting === 'approve'} onClick={() => decide('approve')}>
            Approve
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
