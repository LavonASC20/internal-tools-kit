import { Code } from '@mantine/core';

export function JsonView({ value }: { value: unknown }) {
  if (value === null || value === undefined) return null;
  return <Code block>{JSON.stringify(value, null, 2)}</Code>;
}
