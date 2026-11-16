import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell, Badge, Group, NavLink, Select, Text, Title } from '@mantine/core';
import { useSession } from './session';
import { tools } from './tools';

export function Layout({ children }: { children: ReactNode }) {
  const { me, users, login, can } = useSession();
  const { pathname } = useLocation();

  const items = [
    ...tools.filter((t) => can(t.navAction)).map((t) => ({ to: `/${t.id}`, label: t.title })),
    { to: '/approvals', label: 'Approvals' },
    ...(can('audit.read') ? [{ to: '/audit', label: 'Audit' }] : []),
  ];

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Title order={4}>Internal Tools Kit</Title>
            {import.meta.env.VITE_USE_MOCK === 'true' && <Badge color="yellow">Mock API</Badge>}
          </Group>
          <Group>
            <Text size="sm" c="dimmed">
              {me?.roles.join(', ')}
            </Text>
            <Select
              aria-label="Switch user"
              w={180}
              allowDeselect={false}
              value={me ? String(me.id) : null}
              data={users.map((u) => ({ value: String(u.id), label: u.name }))}
              onChange={(value) => {
                const user = users.find((u) => String(u.id) === value);
                if (user) login(user.id).catch(console.error);
              }}
            />
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {items.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            active={pathname === item.to || pathname.startsWith(`${item.to}/`)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}
