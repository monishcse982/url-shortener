# Cognito management API and UI plan

Status: complete for the current local application scope. Cognito sign-in and management are configured. Production-origin changes are deferred until a hosting target is selected.

## Decisions and contract

- Cognito SPA client uses authorization code with PKCE and the `openid email` scopes. The browser sends the **access token** as a bearer token to management APIs.
- API verifies the JWT signature with the user pool JWKS and checks issuer, expiry, `token_use=access`, client ID, and a human user subject. Ownership uses the token's `sub`.
- The single initial migration requires `owner_sub` on every link. The old database and migration history must be recreated before this migration is applied; deleting rows alone will not rerun `0001_initial`.
- Public redirect stays at `GET /link/{short_code}`. Authenticated create stays at `POST /link/`. Management uses `GET /links`, `GET /links/{short_code}`, `PATCH /links/{short_code}`, and `DELETE /links/{short_code}`. Disable is one-way; no re-enable operation.
- A link detail response includes destination, short URL, title, creation/expiry, visit count/limit, status, and policy type. Password hashes and IP allowlists never appear in the management response.
- The UI lives in `frontend/` (Vite, React, TypeScript, React Router, TanStack Query, `oidc-client-ts`, plain CSS). Frontend config is public build-time configuration; no client secret.

## Tracking

- [x] Add Cognito configuration, JWT verification, and CORS for the SPA origin.
- [x] Add required owner field to the single initial migration.
- [x] Add owner-scoped repository, service, and API operations; protect create and disable.
- [x] Build sign-in, links, and manage-link screens from the supplied mobile references.
- [x] Document local/prod Cognito URLs, API/CORS config, and static deployment.
- [x] Add meaningful API and UI tests, then run lint, typecheck, tests, and build.

## Next live steps

- [x] Recreate the local cluster and apply the consolidated initial migration through the deployment Job.
- [x] Serve the frontend at `http://localhost:5173/` and the API at `http://localhost:8080` with `make app-up`.
- [x] Complete the Cognito sign-in and link-management flow in the browser.
- Deferred with hosting: when a production frontend origin is chosen, register its HTTPS callback and sign-out URLs in Cognito and set the frontend build variables and backend `CORS_ORIGINS` for that origin.

## Verification and limits

- Local tests cover token validation and authenticated API behavior. The configured Cognito flow has also been completed in the browser.
- Production callback/sign-out URLs and CORS settings need review only when a production frontend origin is selected.
