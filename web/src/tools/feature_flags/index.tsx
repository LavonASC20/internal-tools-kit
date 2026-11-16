import type { ToolDefinition } from '../../shell/tools';
import { FlagDetailPage } from './FlagDetailPage';
import { FlagListPage } from './FlagListPage';
import { FLAG_READ } from './types';

const tool: ToolDefinition = {
  id: 'feature_flags',
  title: 'Feature flags',
  navAction: FLAG_READ,
  routes: [
    { index: true, element: <FlagListPage /> },
    { path: ':flagId', element: <FlagDetailPage /> },
  ],
};

export default tool;
