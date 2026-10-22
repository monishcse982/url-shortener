# zipp frontend

Static Vite + React + TypeScript SPA for signing in, creating links, listing them, editing destinations, and disabling links. React Router handles pages, TanStack Query manages API data, and `oidc-client-ts` handles Cognito authorization code with PKCE. The interface uses plain CSS and self-hosted IBM Plex Mono and Doto packages.

## Run locally

From the repository root, run `make app-up` to build the static UI image,
deploy it with the API, and forward both Services. Open
`http://localhost:5173/` and keep the command running. This checks that the
local Cognito and CORS settings agree. The build uses the public values in
`frontend/.env.local`; the UI image contains no app client secret.

To run only the UI against an already forwarded API:

1. Copy `.env.example` to `.env.local` and replace the placeholders. These values are public client configuration. Never add an app client secret to a `VITE_` variable.
2. Start the API on the configured `VITE_API_BASE_URL` and set its `COGNITO_ISSUER`, `COGNITO_CLIENT_ID`, and `CORS_ORIGINS` to match this app.
3. Run `npm ci` and `npm run dev` in `frontend/`. Open `http://localhost:5173/`.

The Cognito app client must be a public SPA client with authorization code grant, PKCE, and `openid email` scopes. Register **exactly** `http://localhost:5173/auth/callback` as an allowed callback and `http://localhost:5173/` as an allowed sign-out URL. The API accepts the Cognito **access token** in `Authorization: Bearer`, and checks the issuer and app client ID.

For production, set `VITE_COGNITO_REDIRECT_URI` and `VITE_COGNITO_LOGOUT_URI` to HTTPS URLs on your frontend origin, register both in the same Cognito app client, and set `CORS_ORIGINS` on the backend to that exact frontend origin. Build with `npm run build` and serve `dist/` from a static host. Configure the host to return `index.html` for SPA paths such as `/links/abc` and `/auth/callback`.

Run `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` before shipping.

## Session storage

OIDC user and PKCE state are kept in `sessionStorage`, so they survive a page reload but are cleared when the tab session ends. This limits persistence compared with `localStorage`, but a script running in the same origin can still read them. Sign out clears the local user, then visits Cognito's logout endpoint. Automatic token renewal uses the refresh token while the Cognito session permits it.

Link creation defaults to a seven-day expiry because the API requires a TTL. Under **options**, owners can set a title, alias, expiry, visit limit, or access policy. Password protected links open an unlock form on the short URL in a browser. API clients can continue sending the `password` header on each redirect request.
