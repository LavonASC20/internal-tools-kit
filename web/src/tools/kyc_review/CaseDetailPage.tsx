import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Alert, Anchor, Badge, Button, Card, Group, Loader, Radio, Stack, Table, Textarea, Title } from '@mantine/core';
import { api, toApiError, type ApiError } from '../../shell/api';
import { Can } from '../../shell/Can';
import { ErrorAlert } from '../../shell/ErrorAlert';
import { useApi } from '../../shell/useApi';
import { statusColor, type KycCase } from './types';

export function CaseDetailPage() {
  const { caseId } = useParams();
  const { data: kycCase, error, loading, reload } = useApi<KycCase>(`/api/kyc/cases/${caseId}`);

  return (
    <Stack>
      <Anchor component={Link} to="..">
        Back to queue
      </Anchor>
      <ErrorAlert error={error} />
      {loading && !kycCase && <Loader />}
      {kycCase && (
        <>
          <Group>
            <Title order={3}>Case {kycCase.id}</Title>
            <Badge color={statusColor[kycCase.status]}>{kycCase.status}</Badge>
          </Group>
          <Card withBorder>
            <Table>
              <Table.Tbody>
                <Row label="Subject" value={kycCase.subject_name} />
                <Row label="National ID" value={kycCase.national_id} />
                <Row label="Date of birth" value={kycCase.date_of_birth} />
                <Row label="Risk flag" value={kycCase.risk_flag} />
              </Table.Tbody>
            </Table>
          </Card>
          <Can action="kyc.decision.propose">
            {kycCase.status === 'open' ? (
              <ProposeForm caseId={String(kycCase.id)} onDone={reload} />
            ) : (
              <Alert color="gray">A decision can be proposed only while the case is open.</Alert>
            )}
          </Can>
        </>
      )}
    </Stack>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Table.Tr>
      <Table.Th w={160}>{label}</Table.Th>
      <Table.Td>{value}</Table.Td>
    </Table.Tr>
  );
}

function ProposeForm({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [decision, setDecision] = useState<string>('');
  const [rationale, setRationale] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post(`/api/kyc/cases/${caseId}/propose`, { decision, rationale });
      onDone();
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card withBorder>
      <form onSubmit={submit}>
        <Stack>
          <Title order={5}>Propose a decision</Title>
          <Radio.Group label="Decision" value={decision} onChange={setDecision} required>
            <Group mt="xs">
              <Radio value="clear" label="Clear" />
              <Radio value="reject" label="Reject" />
            </Group>
          </Radio.Group>
          <Textarea
            label="Rationale"
            required
            autosize
            minRows={3}
            value={rationale}
            onChange={(e) => setRationale(e.currentTarget.value)}
          />
          <ErrorAlert error={error} title="Proposal refused" />
          <Group justify="flex-end">
            <Button type="submit" loading={submitting} disabled={!decision || !rationale.trim()}>
              Submit for approval
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  );
}
