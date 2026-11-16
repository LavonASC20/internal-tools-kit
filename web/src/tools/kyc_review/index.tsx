import type { ToolDefinition } from '../../shell/tools';
import { CaseDetailPage } from './CaseDetailPage';
import { CaseQueuePage } from './CaseQueuePage';

const tool: ToolDefinition = {
  id: 'kyc_review',
  title: 'KYC review',
  navAction: 'kyc.case.read',
  routes: [
    { index: true, element: <CaseQueuePage /> },
    { path: ':caseId', element: <CaseDetailPage /> },
  ],
};

export default tool;
