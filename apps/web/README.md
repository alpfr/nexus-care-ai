# apps/web

Nexus Care AI — Next.js 16 frontend.

Currently scaffolded with the **login flow + dashboard shell**. The clinical surfaces (residents, eMAR, MDS, vitals, AI documentation assistant) land in upcoming tranches.

## What's here

```
apps/web/
├── src/
│   ├── app/
│   │   ├── layout.tsx              root layout, providers
│   │   ├── page.tsx                /  → routes to login or dashboard
│   │   ├── globals.css             Tailwind v4 entry + design tokens
│   │   ├── login/page.tsx          two-step login (facility code → PIN)
│   │   └── dashboard/
│   │       ├── layout.tsx          auth-guarded shell with header
│   │       └── page.tsx            placeholder welcome + tenant info
│   ├── components/
│   │   ├── ui/                     primitives (Button, Input, Card, Logo)
│   │   └── login/                  facility-step, pin-step, pin-keypad, pin-display
│   ├── lib/
│   │   ├── api.ts                  typed fetch wrapper + endpoint helpers
│   │   ├── auth-store.ts           Zustand store, sessionStorage-backed
│   │   └── cn.ts                   classname helper
│   ├── hooks/
│   │   └── use-auth.ts             login / logout / current user
│   └── providers/
│       └── query-provider.tsx      TanStack Query
└── tests/e2e/
    └── login.spec.ts               Playwright login round-trip
```

## Run it

From this directory:

```bash
bun install            # first time only
bun run dev            # http://localhost:3001
```

Or from repo root: `make web` (which runs `bun run dev` here).

The frontend assumes the API is up on `http://localhost:18001`. Bring it up with `make api` from repo root in a separate terminal.

## Login

Default sandbox credentials (created by `make db-seed`):

- Facility code: `demo-sandbox`
- PIN: `246810`

## Tests

```bash
bun run typecheck      # tsc --noEmit
bun run lint           # next lint
bun run test           # vitest unit tests (none yet — components are simple)
bun run test:e2e       # playwright login flow
```

The e2e tests need the API and a seeded sandbox tenant running.

## Design system

Tailwind v4 with a teal-and-slate placeholder palette defined in `src/app/globals.css` via `@theme`. Replace those `--color-brand-*` tokens when real branding lands and the rest of the UI reflows automatically.

Keep using:

- `Button`, `Input`, `Card` from `@/components/ui` instead of raw `<button>` etc.
- `cn()` from `@/lib/cn` for combining classNames
- `useAuth()` from `@/hooks/use-auth` for anything auth-adjacent — never read the store directly
- TanStack Query (`useQuery`, `useMutation`) for any server data — no raw `fetch` in components

## Why no shadcn/ui yet

We bootstrapped just enough primitives (Button, Input, Card) to keep the tranche tight. The shadcn-style "copy components into the repo" pattern lands when we have specific richer components to bring in (Dialog, Form, DataTable, Toast). That'll be tranche 4 or 5 — at the latest, before we port the eMAR.
