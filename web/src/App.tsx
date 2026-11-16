import { Center, Loader, Text } from '@mantine/core';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ApprovalsPage } from './shell/ApprovalsPage';
import { AuditPage } from './shell/AuditPage';
import { Layout } from './shell/Layout';
import { LoginPage } from './shell/LoginPage';
import { useSession } from './shell/session';
import { ToolRoutes } from './shell/ToolRoutes';
import { tools } from './shell/tools';

export function App() {
  const { me, loading, can } = useSession();

  if (loading) {
    return (
      <Center mih="100vh">
        <Loader />
      </Center>
    );
  }
  if (!me) return <LoginPage />;

  const homeTool = tools.find((t) => can(t.navAction));
  const home = homeTool ? `/${homeTool.id}` : can('approvals.read') ? '/approvals' : null;

  return (
    <Layout>
      {/* Remount pages on user switch so no data fetched for the previous user stays on screen. */}
      <Routes key={String(me.id)}>
        <Route
          path="/"
          element={home ? <Navigate to={home} replace /> : <Text c="dimmed">No tools are available for your roles.</Text>}
        />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        {tools.map((t) => (
          <Route key={t.id} path={`/${t.id}/*`} element={<ToolRoutes tool={t} />} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
