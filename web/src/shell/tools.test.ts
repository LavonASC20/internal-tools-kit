import { tools } from './tools';

test('tools are discovered from web/src/tools/*/index.tsx', () => {
  const kyc = tools.find((t) => t.id === 'kyc_review');
  expect(kyc).toBeDefined();
  expect(kyc?.navAction).toBe('kyc.case.read');
  expect(kyc?.routes.length).toBeGreaterThan(0);
});
