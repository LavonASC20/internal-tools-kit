import type { RouteObject } from 'react-router-dom';

// Contract every tool's web/src/tools/<name>/index.tsx default-exports.
export interface ToolDefinition {
  // URL segment, normally the tool folder name, e.g. "kyc_review".
  id: string;
  title: string;
  // The nav entry is shown only when GET /api/me lists this action.
  navAction: string;
  // Routes relative to /<id>.
  routes: RouteObject[];
}

const modules = import.meta.glob<{ default: ToolDefinition }>('../tools/*/index.tsx', { eager: true });

export const tools: ToolDefinition[] = Object.values(modules)
  .map((m) => m.default)
  .sort((a, b) => a.title.localeCompare(b.title));
