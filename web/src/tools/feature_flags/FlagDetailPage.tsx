import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Alert, Anchor, Badge, Button, Card, Group, Loader, Stack, Table, Textarea, Title } from '@mantine/core';
import { api, toApiError, type ApiError } from '../../shell/api';
import { Can } from '../../shell/Can';
import { ErrorAlert } from '../../shell/ErrorAlert';
import { useSession } from '../../shell/session';
import { useApi } from '../../shell/useApi';
import { EnabledBadge } from './EnabledBadge';
import { FLAG_TOGGLE, PROD_PROPOSE, envColor, type Flag } from './types';

export function FlagDetailPage() {
  const { flagId } = useParams();
  const { userName } = useSession();
  const { data: flag, error, loading, reload } = useApi<Flag>(`/api/flags/${flagId}`);

  return (
    <Stack>
      <Anchor component={Link} to="..">
        Back to flags
      </Anchor>
      <ErrorAlert error={error} />
      {loading && !flag && <Loader />}
      {flag && (
        <>
          <Group>
            <Title order={3}>{flag.key}</Title>
            <Badge variant="light" color={envColor[flag.environment]}>
              {flag.environment}
            </Badge>
            <EnabledBadge enabled={flag.enabled} />
          </Group>
          <Card withBorder>
            <Table>
              <Table.Tbody>
                <Row label="Description" value={flag.description} />
                <Row label="Last changed by" value={userName(flag.updated_by)} />
                <Row label="Last changed at" value={new Date(flag.updated_at).toLocaleString()} />
              </Table.Tbody>
            </Table>
          </Card>
          {flag.environment === 'prod' ? (
            flag.pending_request_id !== null ? (
              <Alert color="yellow" title="Waiting for approval">
                Approval request {flag.pending_request_id} must be decided by an engineering lead who did not ask
                for it. See Approvals.
              </Alert>
            ) : (
              <Can action={PROD_PROPOSE}>
                <ProposeForm flag={flag} onDone={reload} />
              </Can>
            )
          ) : (
            <Can action={FLAG_TOGGLE}>
              <ToggleButton flag={flag} onDone={reload} />
            </Can>
          )}
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

const verb = (enabled: boolean) => (enabled ? 'Disable' : 'Enable');

function ToggleButton({ flag, onDone }: { flag: Flag; onDone: () => void }) {
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const toggle = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await api.post(`/api/flags/${flag.id}/toggle`, { enabled: !flag.enabled });
      onDone();
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack>
      <ErrorAlert error={error} title="Toggle refused" />
      <Group>
        <Button onClick={toggle} loading={submitting} color={flag.enabled ? 'gray' : 'green'}>
          {verb(flag.enabled)} in {flag.environment}
        </Button>
      </Group>
    </Stack>
  );
}

function ProposeForm({ flag, onDone }: { flag: Flag; onDone: () => void }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post(`/api/flags/${flag.id}/propose`, { enabled: !flag.enabled, reason });
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
          <Title order={5}>Request a prod toggle</Title>
          <Textarea
            label="Reason"
            required
            autosize
            minRows={2}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
          />
          <ErrorAlert error={error} title="Request refused" />
          <Group justify="flex-end">
            <Button type="submit" loading={submitting} disabled={!reason.trim()}>
              Request {verb(flag.enabled).toLowerCase()} in prod
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  );
}
