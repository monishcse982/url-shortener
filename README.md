# URL Visit Tracker

A FastAPI URL shortener built as a small event-driven system. It creates short links, redirects visitors, publishes visit events to Kafka, and persists visit details asynchronously in PostgreSQL. The repository also includes local Kubernetes deployment, Prometheus/Grafana observability, and repeatable Locust load profiles.

The next planned capabilities are documented in [docs/roadmap.md](docs/roadmap.md).

## Current Capabilities

### Application

- Create short links with generated or custom codes.
- Validate HTTP/HTTPS destinations with Pydantic.
- Configure a title, TTL, and maximum visit count.
- Disable an active short link while preserving its row and visit history.
- Redirect valid short codes with `302 Found`.
- Return `404 Not Found` for unknown or soft-deleted links.
- Return `410 Gone` when a link has expired or reached its visit limit.
- Soft delete expired or exhausted links when they are accessed.
- Capture visit time, user agent, referrer, and IP address.
- Publish visit events to Kafka and persist them asynchronously.
- Send malformed Kafka messages to a dead-letter topic.
- Emit plain-text or JSON logs with correlation IDs.
- Expose FastAPI, application, and Kafka Prometheus metrics at `/metrics`.
- Provide `/dummy-target` for redirect and load testing.

### Infrastructure

- Local Kubernetes cluster through Minikube.
- Helm application and umbrella charts.
- PostgreSQL 18 with persistent storage and initialization SQL.
- Single-node Kafka in KRaft mode managed by Strimzi.
- SCRAM-SHA-512 Kafka authentication.
- Declaratively managed `link.visited` and `link.visited.dlq` topics.
- Prometheus Operator, Prometheus, Grafana, kube-state-metrics, and node exporter.
- Persistent Prometheus storage with two-day retention and a 4 GiB data cap.
- Automatically provisioned URL Visit Tracker Grafana dashboard.

### Tests

- Unit tests for supported link policy validation and creation persistence.
- Locust scenarios for link creation, redirect traffic, and the complete create-and-visit flow.
- Ramp, constant, constant-concurrent, spike, step, and approximate constant-RPS load shapes.
- Named five-minute presets.
- Timestamped HTML, CSV, log, command, and preset artifacts under `reports/load/`.

Each load scenario covers all nine combinations of `public`,
`password_protected`, and `ip_restricted` policies with time-only, visit-only,
and combined expiry/visit-limit settings. Each completed creation task creates
one link per combination; each visit task visits each combination once. The
complete-flow task creates each combination and attempts eleven visits per link,
checking the final redirect or visit-limit response.
Password and IP policies are currently stored during creation;
redirect access checks for those policies are not implemented yet.

Run the unit tests with:

```bash
uv run python -m unittest discover -s tests/unit -v
```

## Request Flow

```text
Create request
    -> FastAPI
    -> PostgreSQL links table

Redirect request
    -> FastAPI
    -> PostgreSQL link lookup and policy checks
    -> Kafka link.visited event
    -> 302 redirect

Kafka consumer
    -> validates LinkVisitedEvent
    -> PostgreSQL visits row
    -> increments links.visit_count
    -> commits Kafka offset

Invalid Kafka payload
    -> link.visited.dlq
```

The Kafka consumer currently starts inside the FastAPI process during application startup. Splitting it into a separately scalable worker is planned future work.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/link/` | Create a short link |
| `GET` | `/link/{short_code}` | Record a visit and return a redirect |
| `DELETE` | `/link/{short_code}` | Soft delete an active short link |
| `GET` | `/dummy-target` | Return a small test response |
| `GET` | `/metrics` | Expose Prometheus metrics |
| `GET` | `/docs` | OpenAPI documentation |

A [Bruno collection](bruno/url-visit-tracker/README.md) provides local
environments and an ordered create, visit, and disable workflow for the API.

Create request:

```json
{
  "url": "https://example.com",
  "ttl_seconds": 86400,
  "max_visits": 10,
  "title": "Example",
  "custom_code": "example-link"
}
```

`title` and `short_code` are optional. `short_code` must contain 3 to 32 letters, numbers, underscores, or hyphens. `ttl_seconds` can be at most 30 days and `max_visits` can be at most 100.

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- A Docker-compatible container runtime such as OrbStack or Docker Desktop
- Minikube
- kubectl
- Helm
- curl and jq for the examples below

Verify the local tools:

```bash
python3 --version
uv --version
docker info
minikube version
kubectl version --client
helm version
```

Install Python dependencies:

```bash
uv sync
```

## Kubernetes Configuration

Create `.env.kubernetes` in the repository root. Environment files are ignored by Git.

```dotenv
APP_SCHEME=http
APP_HOST=localhost
APP_PORT=8080

DATABASE_URL=postgresql+asyncpg://url_tracker_user:<postgres-password>@url-visit-tracker-stack-postgresql:5432/url_visit_tracker
MIGRATION_DATABASE_URL=postgresql+asyncpg://url_tracker_user:<postgres-password>@url-visit-tracker-stack-postgresql:5432/url_visit_tracker

KAFKA_BOOTSTRAP_SERVERS=url-tracker-kafka-bootstrap:9092
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=SCRAM-SHA-512
KAFKA_USERNAME=url-tracker-user
KAFKA_PASSWORD=generated-by-strimzi
KAFKA_CLIENT_ID=url-visit-tracker-api
KAFKA_CONSUMER_GROUP_ID=url-visit-tracker-visits
KAFKA_VISIT_TOPIC=link.visited
KAFKA_VISIT_DLQ_TOPIC=link.visited.dlq

LOG_LEVEL=INFO
LOG_FORMAT=json
```

Use a URL-safe PostgreSQL password or URL-encode it in both database URLs. The Makefile extracts this password to create the PostgreSQL Secret. Strimzi generates the real Kafka password, and `make infra-up` copies it into the application Secret before restarting the application.

## Start the Complete Stack

Validate configuration:

```bash
make validate-env
```

Build the image, create or start Minikube, install infrastructure, run the Tortoise migration Job, deploy the application, synchronize credentials, and wait for readiness:

```bash
make infra-up
```

The first run can take several minutes while container images and Helm charts are downloaded.

Check everything:

```bash
make infra-status
make migration-status
```

Useful direct checks:

```bash
kubectl --context minikube get pods -n url-tracker
kubectl --context minikube get kafka,kafkauser,kafkatopic -n url-tracker
kubectl --context minikube get pods -n observability
```

## Makefile Workflow

Use these targets for the usual development cycle:

### Start and stop a work session

Start an existing Minikube profile and check the stack:

```bash
make infra-start
make infra-status
```

Keep the application and local dependency tunnels open in a separate terminal:

```bash
make port-forward-all
```

This forwards the application, PostgreSQL, Valkey, Grafana, and Prometheus. Press `Ctrl+C` in that terminal to stop the forwards. To forward only the app, use `make port-forward-app`.

When finished, stop Minikube without deleting its cluster data:

```bash
make infra-stop
```

### Apply application code changes

After changing Python code or the Docker image contents, rebuild and load the image into Minikube, then restart the Deployment:

```bash
make image-load
make restart
```

`image-load` starts Minikube if needed, builds `url-visit-tracker:local`, and loads it into the cluster. It does not restart the running application by itself.

### Apply configuration or chart changes

After changing Helm chart values or Kubernetes environment configuration, validate the environment and apply the release:

```bash
make validate-env
make deploy
```

If you changed values stored in Secrets, restart the application afterward so it reads the updated environment:

```bash
make restart
```

`make deploy` also refreshes the application, PostgreSQL, and Valkey Secrets from `$(ENV_FILE)`, installs or upgrades Strimzi and monitoring, validates the charts, and upgrades the application release. The application chart runs Tortoise migrations in a Helm Job after PostgreSQL is ready on first install and before application upgrades. Helm waits for this Job to complete; a failed migration fails the deployment. The PostgreSQL chart does not create application tables itself; Tortoise migration files are the schema source of truth. For standalone local development, `make migrate` applies migrations using `MIGRATION_DATABASE_URL` from the local `.env` (or the shell environment). Use `make migration-status` after deployment to list the versions recorded by Tortoise in the cluster database.

### Inspect and troubleshoot

```bash
make status                    # Application and infrastructure resources
make logs                      # Follow application and embedded consumer logs
make diagnose-port-forward     # Pod health, endpoints, events, and recent logs
make monitoring-status         # Prometheus and Grafana resources
```

For Grafana or Prometheus access without opening all tunnels, use `make grafana-forward` or `make prometheus-forward` in a dedicated terminal.

### Fresh setup and teardown

For a new or deleted cluster, use the full setup target. It builds and loads the app image, deploys the stack, waits for dependencies, synchronizes the Kafka credential, and restarts the application:

```bash
make infra-up
```

This is intentionally more involved than `make infra-start`; use it for initial provisioning, not every work session.

The teardown targets have different effects:

- `make infra-stop` stops Minikube and preserves the cluster for the next session.
- `make uninstall` removes the application, monitoring, and Strimzi Helm releases but keeps the Minikube profile. Check the chart's persistent-volume behavior before relying on database data being retained.
- `make cluster-delete CONFIRM=delete` deletes the Minikube profile and its cluster data.

Run `make help` to list all targets. Common overrides include `PROFILE`, `NAMESPACE`, `ENV_FILE`, and `LOCAL_PORT`; for example, `make port-forward-app LOCAL_PORT=8080`.

## Access the Application

Keep this command running in its own terminal. It forwards the app and local dependencies:

```bash
make port-forward-all LOCAL_PORT=8080
```

Available locally:

- API: <http://localhost:8080>
- OpenAPI: <http://localhost:8080/docs>
- Metrics: <http://localhost:8080/metrics>

Create and visit a link:

```bash
response=$(curl -fsS -X POST http://localhost:8080/link/ \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://example.com",
    "ttl_seconds": 3600,
    "max_visits": 10,
    "title": "Example"
  }')

echo "$response" | jq

short_code=$(echo "$response" | jq -r '.shortened_url | split("/") | last')
curl -i --max-redirs 0 "http://localhost:8080/link/$short_code"
```

Follow application and embedded consumer logs:

```bash
make logs
```

## Grafana and Prometheus

Print the generated Grafana credentials:

```bash
make grafana-password
```

Forward Grafana in a dedicated terminal:

```bash
make grafana-forward
```

Open <http://localhost:3000> and select the **URL Visit Tracker** dashboard.

Forward Prometheus in another terminal:

```bash
make prometheus-forward
```

Open <http://localhost:9090>. A useful target query is:

```promql
up{namespace="url-tracker", service="url-visit-tracker-stack"}
```

The local profile defaults to four CPUs, 8 GiB of memory, and a 25 GiB disk.
Prometheus stores metrics on a 5 GiB persistent volume, retains up to two days
of data, and normally scrapes every 15 seconds. To sample every five seconds
for a load run, deploy with:

```bash
make deploy SCRAPE_INTERVAL=5s
```

Run `make deploy` again afterward to restore the 15-second interval. Changing
from the old temporary Prometheus storage to the persistent volume starts with
an empty metrics database; existing metrics in the temporary volume are not
transferred.

## Kafka Topics

The Helm release creates Strimzi `KafkaTopic` resources. The Strimzi Topic Operator then creates the broker topics automatically.

```bash
kubectl --context minikube get kafkatopics -n url-tracker
```

Wait for both topics:

```bash
kubectl --context minikube wait \
  --for=condition=Ready \
  kafkatopic/link-visited \
  kafkatopic/link-visited-dlq \
  -n url-tracker \
  --timeout=60s
```

The Kubernetes resource names use hyphens, while the Kafka topic names are `link.visited` and `link.visited.dlq`.

## Load Tests

The scenarios default to `http://localhost:8080`, matching `APP_PORT` and the local application port-forward. Keep `make port-forward-all` running before starting a test; use `--base-url` to override the target when needed.

List presets:

```bash
./tests/load/run-load-test.sh --list
```

Run a preset:

```bash
./tests/load/run-load-test.sh happy_path_ramp_user_100user_5minutes
```

Available presets:

```text
create_short_link_constant_user_50user_5minutes
create_short_link_ramp_user_100user_5minutes
happy_path_ramp_user_100user_5minutes
visit_short_link_constant_user_100user_5minutes
visit_short_link_spike_user_200user_5minutes
visit_short_link_step_user_250user_5minutes
```

Each run writes to:

```text
reports/load/<preset-name>/<timestamp>/
```

The directory contains the HTML report, CSV data, Locust log, executed command, and a copy of the selected preset.

## Code Quality

Pull requests and pushes run the checks in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml): locked Python dependency
installation, Ruff lint and formatting, unit tests, Helm lint and rendering,
Docker image build, and secret scans of committed files and Git history. The
workflow has read-only repository permissions and does not deploy. To prevent
merges when a check fails, require these job checks in the GitHub branch
protection settings for `master`.

Run Ruff checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

Apply formatting:

```bash
uv run ruff format .
```

Restore the chart dependencies from `Chart.lock`, then lint and render the manifests:

```bash
make chart-validate
```

## Direct Local Development

To run FastAPI directly instead of using the Kubernetes application pod, provide a `.env` whose PostgreSQL and Kafka addresses are reachable from the host, then run:

```bash
uv run uvicorn app.main:app --reload --host localhost --port 8000
```

The embedded Kafka consumer starts with the application. End-to-end visits therefore require both PostgreSQL and Kafka to be reachable with the credentials in `.env`.

## Common Make Commands

List all commands:

```bash
make help
```

| Command | Purpose |
| --- | --- |
| `make infra-up` | Build, deploy, synchronize secrets, and wait for the complete stack |
| `make infra-start` | Start an existing stopped Minikube profile |
| `make infra-stop` | Stop Minikube while preserving cluster state |
| `make infra-status` | Show cluster, application, and monitoring status |
| `make image-build` | Build the local application image |
| `make image-load` | Build and load the image into Minikube |
| `make chart-validate` | Update dependencies, lint charts, and render manifests |
| `make deploy` | Upgrade or install the application stack |
| `make infra-ready` | Wait for dependencies, synchronize Kafka credentials, and restart the app |
| `make migration-status` | List Tortoise migration versions recorded in cluster PostgreSQL |
| `make restart` | Restart and wait for the application Deployment |
| `make logs` | Follow application and consumer logs |
| `make port-forward LOCAL_PORT=8080` | Expose the API locally |
| `make monitoring-status` | Show Prometheus and Grafana resources |
| `make grafana-password` | Print generated Grafana credentials |
| `make grafana-forward` | Expose Grafana at port 3000 |
| `make prometheus-forward` | Expose Prometheus at port 9090 |
| `make uninstall` | Uninstall Helm releases while preserving the Minikube profile |
| `make cluster-delete CONFIRM=delete` | Permanently delete the Minikube profile and its data |

After application code changes, the simplest complete rebuild and rollout is:

```bash
make infra-up
```

## Stop or Remove the Environment

Stop the cluster and preserve its workloads and persistent data:

```bash
make infra-stop
```

Start it again:

```bash
make infra-start
```

Remove the Helm releases but retain the Minikube profile:

```bash
make uninstall
```

Delete the complete Minikube cluster and all data stored inside it:

```bash
make cluster-delete CONFIRM=delete
```

## Before Publishing to GitHub

Keep `.env`, `.env.kubernetes`, local IDE settings, virtual environments, generated
reports, and packaged Helm charts out of commits. The repository's `.gitignore`
excludes these paths; Git can still stage an ignored file when forced with
`git add -f`, so review the staged file list.

Enable the repository-local hooks in a new clone:

```bash
sh scripts/install-git-hooks.sh
```

This sets `core.hooksPath` to the tracked `.githooks/` directory. Git ignores
`.git/hooks/` while that setting is active. Keep the executable `pre-commit`
and `pre-push` files in `.githooks/` so they are available in new clones.

The commit hook checks staged whitespace and scans every staged file for
credential file paths and likely hard-coded secrets. The push hook scans the
history being pushed, including earlier versions of files. Both hooks use
Python 3 and print file locations without printing matched secret values.
These pattern checks help catch mistakes but are not a complete secret audit.

Before the first commit, review exactly what Git will include:

```bash
python3 scripts/check-git-content.py --working-tree
git add .
git diff --cached --stat
git diff --cached --check
python3 scripts/check-git-content.py --staged
```

Commit `uv.lock` and the source charts, but leave real credentials and load
reports local. If a credential is ever committed, remove it from Git history
and rotate it before publishing; adding it to `.gitignore` later is not enough.

## Roadmap

The disable API is implemented. The remaining implementation sequence is:

1. Atomic visit admission
2. Redis redirect cache
3. Rate limiting protection
4. One-time and protected links

See [docs/roadmap.md](docs/roadmap.md) for contracts, design constraints, and verification criteria.
