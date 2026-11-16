# web

Vite + React + TypeScript + Mantine (defaults only).

```
npm install
npm run dev        # proxies /api to API_TARGET or BACKEND_URL (default http://localhost:8000)
npm run dev:mock   # serves /api from the in-browser mock, no backend needed
npm run typecheck
npm run build
npm test
```

## Layout

- `src/shell/`: login picker, user switcher, nav, approvals inbox, audit view, API client, `useSession().can()` and `<Can>`.
- `src/tools/<name>/index.tsx`: default-exports a `ToolDefinition` (`id`, `title`, `navAction`, `routes`). The shell finds it with `import.meta.glob`, so adding a tool needs no shell edit.
- `src/tools/<name>/mock.ts`: optional mock handlers for that tool's routes, also discovered by glob.
- `src/mock/`: the mock layer. It patches `fetch` for `/api/*` only when `VITE_USE_MOCK=true` and is not included in normal builds. Mock state lives in `localStorage` (`itk-mock-db-v1`); clear it to reseed.

## Permissions

The frontend never decides permissions. A control renders only when `GET /api/me` lists its action:
nav entries use the tool's `navAction` (audit uses `audit.read`), the propose form uses `kyc.decision.propose`,
and the approvals Decide button uses the request's `action`. Everything else (self-approval, state, masking) is enforced by the API and surfaced as an error.
