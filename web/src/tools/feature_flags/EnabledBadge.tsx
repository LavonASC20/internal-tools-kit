import { Badge } from '@mantine/core';

export function EnabledBadge({ enabled }: { enabled: boolean }) {
  return <Badge color={enabled ? 'green' : 'gray'}>{enabled ? 'on' : 'off'}</Badge>;
}
