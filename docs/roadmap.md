# Shawty Project Status and Roadmap

## Current status

The planned application scope is complete. The project runs locally on Minikube and includes the API, management UI, Cognito authentication, visit-event processing, observability, and repeatable API load tests. EKS hosting is a separate learning exercise and is deferred; it is not a blocker for calling the current project complete.

## Completed capabilities

- [x] Create, list, edit, and disable owner-managed short links.
- [x] Authenticate the management UI and API with Amazon Cognito.
- [x] Support public, password-protected, and IP-restricted links.
- [x] Enforce expiry and visit limits, including atomic admission for limited links.
- [x] Cache eligible public redirects in Redis and invalidate changed links.
- [x] Publish visit events to Kafka and persist visit details asynchronously in PostgreSQL.
- [x] Expose application and Kafka metrics, with Prometheus/Grafana dashboards.
- [x] Run the application stack locally through Minikube and Helm.
- [x] Exercise API behavior with unit tests and repeatable Locust load profiles.
- [x] Run GitHub Actions checks for frontend, Python, Helm, image builds, and secret scanning.

## Deferred learning work

These are optional follow-up exercises, not unfinished project requirements:

- Deploy the stack to EKS and use ECR images. See [the EKS learning plan](eks-learning-plan.md).
- Add browser end-to-end tests for real UI journeys. Current frontend tests cover UI behavior with mocked authentication and API responses; API load testing is already covered by Locust.
- Improve behavior when Redis is unavailable. Redis is currently checked during application startup and cache operations are not treated as best-effort.
- Study durable Kafka publishing and idempotent visit processing. Visit-limit admission is committed to PostgreSQL before the visit event is delivered, and visit rows do not currently deduplicate by event ID.
- Validate IP-restricted links behind a trusted reverse proxy before using that feature in a proxied deployment.

## Completion note

The current local project scope is complete. No additional feature work is planned now. Reopen the deferred items only when they support a specific learning goal or deployment need.
