import { useRoutes } from 'react-router-dom';
import type { ToolDefinition } from './tools';

export function ToolRoutes({ tool }: { tool: ToolDefinition }) {
  return useRoutes(tool.routes);
}
