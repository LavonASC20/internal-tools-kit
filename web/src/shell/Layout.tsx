import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell, Badge, Burger, Group, NavLink, Select, Text, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useSession } from './session';
import { tools } from './tools';

export function Layout({ children }: { children: ReactNode }) {
  const { me, users, login, can } = useSession();
  const { pathname } = useLocation();
  const [navOpened, { toggle: toggleNav, close: closeNav }] = useDisclosure(false);

  const items = [
    ...tools.filter((t) => can(t.navAction)).map((t) => ({ to: `/${t.id}`, label: t.title })),
    ...(can('approvals.read') ? [{ to: '/approvals', label: 'Approvals' }] : []),
    ...(can('audit.read') ? [{ to: '/audit', label: 'Audit' }] : []),
  ];

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !navOpened } }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap">
            <Burger opened={navOpened} onClick={toggleNav} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <Title order={4}>Internal Tools Kit</Title>
            {import.meta.env.VITE_USE_MOCK === 'true' && <Badge color="yellow">Mock API</Badge>}
          </Group>
          <Group wrap="nowrap">
            <Text size="sm" c="dimmed" visibleFrom="sm">
              {me?.roles.join(', ')}
            </Text>
            <Select
              aria-label="Switch user"
              w={{ base: 120, sm: 180 }}
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
            onClick={closeNav}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}
