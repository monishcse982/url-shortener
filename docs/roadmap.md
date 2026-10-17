# Shawty Roadmap

This roadmap focuses on behavior and correctness rather than additional analytics. The work starts with an explicit disable operation, then strengthens the redirect path before adding caching and richer link policies.

## Implementation Order

1. Disable API (core behavior implemented)
2. Atomic visit admission
3. Redis redirect cache
4. User management
5. Policy-driven links

The ordering is intentional. Atomic admission is the foundation for one-time links, Redis can then support redirect caching, and user management provides the ownership and authorization model for managing links.

## 0. Disable API (Core Behavior Implemented)

Add an explicit management operation that prevents a link from being used without deleting its row or visit history.

The route, soft-delete behavior, centralized `404` response, and unit coverage are implemented. Authorization, a dedicated disable metric, and a database-backed integration test remain before this milestone is production-ready.

Suggested contract:

```http
DELETE /link/{short_code}
```

Expected behavior:

- An active link is soft deleted and returns `204 No Content`.
- Disabling an already-disabled link returns `404 Not Found` because it is no longer active.
- A code that has never existed returns `404 Not Found`.
- Subsequent redirect attempts do not publish visit events.
- Existing visit records remain available.
- A structured log and Prometheus counter record the operation.

The current model can initially use `is_deleted`. Before adding richer link policies and cache invalidation, replace or supplement it with an explicit status such as `ACTIVE`, `DISABLED`, `EXPIRED`, `VISIT_LIMIT_REACHED`, and `REVOKED` so different terminal states are not collapsed into one flag.

Authorization must be decided before this endpoint is exposed outside local development. A short code by itself is not proof that the caller owns the link. An API key, owner identity, or per-link management token are reasonable later options.

Verification:

- Disable an active link and confirm redirects stop.
- Repeat the disable request and confirm it returns `404 Not Found`.
- Confirm no new Kafka visit event or `visits` row is produced after disabling.
- Confirm historical visits remain in PostgreSQL.

## 1. Atomic Visit Admission

Move the decision to accept a visit into one atomic database statement. The current read-then-publish flow can allow concurrent requests to exceed `max_visits` because Kafka updates the count after the redirect request.

The repository operation should update only when the link is active, unexpired, and below its visit limit:

```sql
UPDATE links
SET visit_count = visit_count + 1
WHERE short_code = :short_code
  AND status = 'ACTIVE'
  AND expires_at > now()
  AND visit_count < max_visits
RETURNING id, original_url, visit_count, max_visits;
```

The redirect service should publish a Kafka event only after admission succeeds. The Kafka consumer should record visit details but should no longer increment the authoritative count.

Verification:

- Send more concurrent requests than `max_visits`.
- Confirm exactly `max_visits` requests receive redirects.
- Confirm all later requests receive `410 Gone`.
- Confirm the database counter never exceeds the configured limit.
- Confirm the number of accepted Kafka events matches the admitted visits.

## 2. Redis Redirect Cache

Use Redis as a cache for relatively static redirect data such as link ID, destination, status, and expiry. PostgreSQL remains the source of truth.

Use a cache-aside flow:

1. Read `link:{short_code}` from Redis.
2. On a miss, load the active link from PostgreSQL.
3. Cache it with a TTL no longer than the link's remaining lifetime.
4. Continue to use atomic visit admission for visit-limited links.

Required behavior:

- Delete the cache entry when a link is disabled or changes state.
- Use short negative-cache entries for unknown codes to protect PostgreSQL from random-code scans.
- Fall back to PostgreSQL when Redis is unavailable.
- Track cache hits, misses, invalidations, and Redis errors.
- Prevent cache stampedes for unusually hot uncached links if they become observable.

Verification:

- Confirm the first request misses and later requests hit Redis.
- Disable a cached link and confirm it cannot redirect.
- Let a cached link expire and confirm it is not served beyond its TTL.
- Stop Redis and confirm redirects fall back to PostgreSQL.
- Confirm visit limits remain correct under concurrent cached requests.

## 3. User Management

Add user identity and authentication so link management operations can be authorized to their owners.

Initial scope:

- Define the user identity and authentication mechanism.
- Associate created links with their owner.
- Require authentication and ownership checks for link creation, updates, and disable operations.
- Keep public redirect access available without requiring a user account.
- Return consistent authorization errors without exposing another user's link data.

Verification:

- Confirm unauthenticated management requests are rejected.
- Confirm an authenticated owner can manage their links.
- Confirm one user cannot manage another user's links.
- Confirm public redirects continue to work without authentication.

## 4. Policy-Driven Links

### One-Time Links

One-time links are a policy on top of atomic admission. Model them explicitly rather than treating them only as `max_visits = 1` in the API.

Expected behavior:

- Exactly one concurrent request can claim the link.
- The successful request receives the redirect.
- Every later request receives `410 Gone`.
- The terminal state is `VISIT_LIMIT_REACHED` or `CONSUMED`.
- The accepted visit event is published once.

### Protected Links

Protected links require a successful secret check before redirect admission.

Design requirements:

- Never store the password in plaintext; store a modern password hash.
- Do not put the password in a query string because URLs are commonly logged.
- Use a form submission or API request to exchange the password for a short-lived authorization token or cookie.
- Avoid revealing whether a failure was caused by an unknown link or incorrect password where that distinction creates an enumeration risk.
- Publish visit events only after protection and admission checks succeed.

Verification:

- Confirm incorrect passwords cannot redirect or create visit events.
- Confirm correct passwords allow admission.
- Confirm protected one-time links still permit only one successful concurrent visit.
- Confirm stored data contains only password hashes.

## Cross-Cutting Expectations

Each milestone should include:

- Repository and service-level tests for its core rules.
- At least one concurrent or failure-path test where relevant.
- Prometheus metrics with low-cardinality labels.
- Structured logs carrying the existing correlation ID.
- Helm values and Kubernetes resources for any new process or dependency.
- A load-test preset that exercises the new behavior when load is relevant.
- README updates when commands or infrastructure change.
