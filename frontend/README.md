# CodeSentinel — Frontend (React + Vite + TypeScript)

Real single-page app, matching the stack described in the internship
report (§3.2.3, §3.10): **React 19 + Vite + TypeScript**, consuming the
FastAPI backend's REST API (`app/api.py`, `app/dashboard.py`) over
`fetch`, with the session JWT kept in `localStorage` and sent as
`Authorization: Bearer <token>` (no cookies — see report §3.9.1).

## Structure

```
src/
  lib/
    api.ts          typed fetch client (one function per backend endpoint)
    types.ts         TypeScript types mirroring the backend's response shapes
  context/
    AuthContext.tsx   current user, token capture from OAuth redirect, logout
    ThemeContext.tsx   light/dark mode, persisted + respects OS preference
    ToastContext.tsx   toast notifications (replaces old alert())
  components/         Sidebar, StatCard, ScoreTrendChart (Recharts),
                       IssuesDonut (Recharts), ConnectRepoModal, etc.
  pages/               Landing, Dashboard, RepoDetail, Admin, TestAgent, ConfigPage
```

## Development

Run the backend first (`uvicorn app.main:app --reload` from the project
root), then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

This starts Vite's dev server (default `http://localhost:5173`) with hot
module reloading. Requests to `/api`, `/auth`, `/webhook`, and `/health`
are proxied to the FastAPI backend (default `http://localhost:8000` —
override with `VITE_BACKEND_URL` if your backend runs elsewhere).

## Production build

```bash
cd frontend
npm run build
```

This outputs `frontend/dist/`. **FastAPI serves this directory directly**
(see `app/main.py`): static assets are mounted at `/assets`, and any other
GET request that doesn't match an API/auth/webhook route falls back to
`index.html`, so React Router can handle client-side routes like
`/dashboard/repos/acme%2Fapi-gateway` without a server round trip per route.

In other words: build once, then just run the FastAPI server as usual —
there's no separate frontend server needed in production.

## Type checking

```bash
npx tsc -b
```

Run automatically as part of `npm run build`.
