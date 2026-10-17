SHELL := /bin/bash
.DEFAULT_GOAL := help
.NOTPARALLEL:

PROFILE ?= minikube
NAMESPACE ?= url-tracker
RELEASE ?= url-visit-tracker-stack
IMAGE ?= url-visit-tracker
IMAGE_TAG ?= local
ENV_FILE ?= .env.kubernetes
LOCAL_PORT ?= $(or $(shell awk -F= '$$1 == "APP_PORT" { print $$2; exit }' $(ENV_FILE) 2>/dev/null),8000)
POSTGRES_LOCAL_PORT ?= 5433
VALKEY_LOCAL_PORT ?= 6380

MINIKUBE_CPUS ?= 4
MINIKUBE_MEMORY ?= 8192
MINIKUBE_DISK_SIZE ?= 25g
MINIKUBE_DRIVER ?= docker

APP_CHART := deploy/charts/url-visit-tracker
STACK_CHART := deploy/charts/url-visit-tracker-stack
RENDERED_MANIFEST := /tmp/url-visit-tracker-stack-rendered.yaml
KUBECTL := kubectl --context $(PROFILE)
HELM_CONTEXT := --kube-context $(PROFILE)
POSTGRES_SECRET := url-visit-tracker-postgresql
POSTGRES_STATEFULSET := $(RELEASE)-postgresql
VALKEY_SECRET := url-visit-tracker-valkey
VALKEY_DEPLOYMENT := valkey
STRIMZI_RELEASE := strimzi-operator
STRIMZI_CHART := oci://quay.io/strimzi-helm/strimzi-kafka-operator
STRIMZI_VERSION := 1.2.0
STRIMZI_VALUES := deploy/kafka/strimzi-operator-values.yaml
KAFKA_CLUSTER := url-tracker
KAFKA_USER := url-tracker-user
MONITORING_NAMESPACE ?= observability
MONITORING_RELEASE ?= monitoring
MONITORING_CHART := oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack
MONITORING_VERSION := 91.4.1
MONITORING_VALUES := deploy/observability/values-local.yaml
SCRAPE_INTERVAL ?= 15s
GRAFANA_SERVICE := $(MONITORING_RELEASE)-grafana
PROMETHEUS_SERVICE := $(MONITORING_RELEASE)-kube-prometheus-prometheus
GRAFANA_PORT ?= 3000
PROMETHEUS_PORT ?= 9090

.PHONY: help unit-test coverage infra-up infra-start infra-stop infra-status cluster-up cluster-stop cluster-status image-build image-load validate-env namespace secret postgres-secret valkey-secret kafka-operator monitoring-install monitoring-status grafana-password grafana-forward prometheus-forward chart-deps chart-validate deploy wait-infra sync-kafka-password infra-ready migration-status status logs port-forward port-forward-app port-forward-all diagnose-port-forward restart uninstall cluster-delete makemigrations migrate

help: ## Show the available commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [VARIABLE=value]\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nCommon overrides:\n"
	@printf "  PROFILE=%s NAMESPACE=%s ENV_FILE=%s LOCAL_PORT=%s\n" "$(PROFILE)" "$(NAMESPACE)" "$(ENV_FILE)" "$(LOCAL_PORT)"

unit-test: ## Run unit tests while collecting line and branch coverage.
	uv run --locked coverage run -m unittest discover -s tests/unit -v

coverage: unit-test ## Run unit tests and print the coverage summary.
	uv run --locked coverage report

infra-up: image-load infra-ready status ## Start Minikube and deploy the complete application stack.

infra-start: cluster-up status ## Start the existing Minikube profile without rebuilding.

infra-stop: cluster-stop ## Stop Minikube while preserving cluster data.

infra-status: cluster-status status monitoring-status ## Show Minikube, Helm, and Kubernetes status.

cluster-up: ## Create or start the Minikube profile.
	minikube start --profile $(PROFILE) --driver $(MINIKUBE_DRIVER) --cpus $(MINIKUBE_CPUS) --memory $(MINIKUBE_MEMORY) --disk-size $(MINIKUBE_DISK_SIZE)
	minikube update-context --profile $(PROFILE)

cluster-stop: ## Stop the Minikube profile without deleting it.
	minikube stop --profile $(PROFILE)

cluster-status: ## Show Minikube and Kubernetes node status.
	minikube status --profile $(PROFILE)
	$(KUBECTL) get nodes -o wide

image-build: ## Build the local application image.
	docker build -t $(IMAGE):$(IMAGE_TAG) .

image-load: cluster-up image-build ## Load the application image into Minikube.
	minikube image load $(IMAGE):$(IMAGE_TAG) --profile $(PROFILE)
	@minikube image ls --profile $(PROFILE) | grep -F "$(IMAGE):$(IMAGE_TAG)"

validate-env: ## Check that the env file exists and contains no duplicate keys.
	@test -f "$(ENV_FILE)" || { echo "Missing environment file: $(ENV_FILE)"; exit 1; }
	@duplicates=$$(awk -F= '/^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/ { key=$$1; sub(/^[[:space:]]*export[[:space:]]+/, "", key); gsub(/[[:space:]]/, "", key); count[key]++ } END { for (key in count) if (count[key] > 1) print key " (" count[key] " definitions)" }' "$(ENV_FILE)"); if [ -n "$$duplicates" ]; then echo "Duplicate environment keys found:"; echo "$$duplicates"; exit 1; fi

namespace: cluster-up ## Create the application namespace when it does not exist.
	$(KUBECTL) create namespace $(NAMESPACE) --dry-run=client -o yaml | $(KUBECTL) apply -f -

secret: namespace validate-env ## Create or update the application Secret from the env file.
	$(KUBECTL) create secret generic url-visit-tracker-env --namespace $(NAMESPACE) --from-env-file=$(ENV_FILE) --dry-run=client -o yaml | $(KUBECTL) apply -f -

postgres-secret: namespace validate-env ## Create PostgreSQL credentials from DATABASE_URL.
	@database_url=$$(awk -F= '$$1 == "DATABASE_URL" { print substr($$0, index($$0, "=") + 1); exit }' "$(ENV_FILE)"); password=$$(printf '%s' "$$database_url" | sed -E 's#^[^:]+://[^:]+:([^@]+)@.*#\1#'); if [ -z "$$password" ] || [ "$$password" = "$$database_url" ]; then echo "Could not extract the PostgreSQL password from DATABASE_URL"; exit 1; fi; $(KUBECTL) create secret generic $(POSTGRES_SECRET) --namespace $(NAMESPACE) --from-literal=postgres-password="$$password" --from-literal=password="$$password" --dry-run=client -o yaml | $(KUBECTL) apply -f -

valkey-secret: namespace validate-env ## Create Valkey credentials from CACHE_URL.
	@cache_url=$$(awk -F= '$$1 == "CACHE_URL" { print substr($$0, index($$0, "=") + 1); exit }' "$(ENV_FILE)"); password=$$(printf '%s' "$$cache_url" | sed -E 's#^[^:]+://([^:]*:)?([^@]+)@.*#\2#'); if [ -z "$$password" ] || [ "$$password" = "$$cache_url" ]; then echo "Could not extract the Valkey password from CACHE_URL"; exit 1; fi; $(KUBECTL) create secret generic $(VALKEY_SECRET) --namespace $(NAMESPACE) --from-literal=default="$$password" --dry-run=client -o yaml | $(KUBECTL) apply -f -

kafka-operator: namespace ## Install or upgrade the Strimzi Kafka operator.
	helm upgrade --install $(STRIMZI_RELEASE) $(STRIMZI_CHART) $(HELM_CONTEXT) --version $(STRIMZI_VERSION) --namespace $(NAMESPACE) --values $(STRIMZI_VALUES) --wait --timeout 10m

monitoring-install: cluster-up ## Install or upgrade Prometheus and Grafana.
	helm upgrade --install $(MONITORING_RELEASE) $(MONITORING_CHART) $(HELM_CONTEXT) --version $(MONITORING_VERSION) --namespace $(MONITORING_NAMESPACE) --create-namespace --values $(MONITORING_VALUES) --set prometheus.prometheusSpec.scrapeInterval=$(SCRAPE_INTERVAL) --set prometheus.prometheusSpec.evaluationInterval=$(SCRAPE_INTERVAL) --wait --timeout 15m

monitoring-status: ## Show Prometheus and Grafana resources.
	helm list $(HELM_CONTEXT) --namespace $(MONITORING_NAMESPACE)
	$(KUBECTL) get pods,services --namespace $(MONITORING_NAMESPACE) -o wide

grafana-password: ## Print the local Grafana username and generated password.
	@printf "Username: "; $(KUBECTL) get secret $(GRAFANA_SERVICE) --namespace $(MONITORING_NAMESPACE) -o jsonpath='{.data.admin-user}' | base64 --decode; printf '\n'
	@printf "Password: "; $(KUBECTL) get secret $(GRAFANA_SERVICE) --namespace $(MONITORING_NAMESPACE) -o jsonpath='{.data.admin-password}' | base64 --decode; printf '\n'

grafana-forward: ## Forward Grafana to localhost.
	@echo "Grafana: http://localhost:$(GRAFANA_PORT)"
	$(KUBECTL) port-forward --namespace $(MONITORING_NAMESPACE) service/$(GRAFANA_SERVICE) $(GRAFANA_PORT):80

prometheus-forward: ## Forward Prometheus to localhost.
	@echo "Prometheus: http://localhost:$(PROMETHEUS_PORT)"
	$(KUBECTL) port-forward --namespace $(MONITORING_NAMESPACE) service/$(PROMETHEUS_SERVICE) $(PROMETHEUS_PORT):9090

chart-deps: ## Refresh the umbrella chart dependencies and lock file.
	helm dependency update $(STACK_CHART)
	helm dependency list $(STACK_CHART)

chart-validate: ## Build locked dependencies, lint both charts, and render the complete stack.
	helm dependency build $(STACK_CHART)
	helm lint $(APP_CHART)
	helm lint $(STACK_CHART)
	helm template $(RELEASE) $(STACK_CHART) $(HELM_CONTEXT) --namespace $(NAMESPACE) --set url-visit-tracker.monitoring.serviceMonitor.interval=$(SCRAPE_INTERVAL) --set valkey.metrics.serviceMonitor.interval=$(SCRAPE_INTERVAL) > $(RENDERED_MANIFEST)

deploy: secret postgres-secret valkey-secret kafka-operator monitoring-install chart-validate ## Install or upgrade the umbrella Helm release.
	helm upgrade --install $(RELEASE) $(STACK_CHART) $(HELM_CONTEXT) --namespace $(NAMESPACE) --set url-visit-tracker.monitoring.serviceMonitor.interval=$(SCRAPE_INTERVAL) --set valkey.metrics.serviceMonitor.interval=$(SCRAPE_INTERVAL) --wait --timeout 5m

wait-infra: ## Wait for PostgreSQL, Kafka, topics, and the Kafka user.
	$(KUBECTL) rollout status statefulset/$(POSTGRES_STATEFULSET) --namespace $(NAMESPACE) --timeout=10m
	$(KUBECTL) wait --namespace $(NAMESPACE) --for=condition=complete job/$(RELEASE)-migrate --timeout=5m
	$(KUBECTL) rollout status deployment/$(VALKEY_DEPLOYMENT) --namespace $(NAMESPACE) --timeout=5m
	$(KUBECTL) wait kafka/$(KAFKA_CLUSTER) --namespace $(NAMESPACE) --for=condition=Ready --timeout=10m
	$(KUBECTL) wait kafkauser/$(KAFKA_USER) --namespace $(NAMESPACE) --for=condition=Ready --timeout=5m
	$(KUBECTL) wait kafkatopic/link-visited --namespace $(NAMESPACE) --for=condition=Ready --timeout=5m
	$(KUBECTL) wait kafkatopic/link-visited-dlq --namespace $(NAMESPACE) --for=condition=Ready --timeout=5m

sync-kafka-password: wait-infra ## Copy the generated Kafka password into the application Secret.
	@password_b64=$$($(KUBECTL) get secret $(KAFKA_USER) --namespace $(NAMESPACE) -o jsonpath='{.data.password}'); if [ -z "$$password_b64" ]; then echo "Kafka password was not generated"; exit 1; fi; $(KUBECTL) patch secret url-visit-tracker-env --namespace $(NAMESPACE) --type=merge -p '{"data":{"KAFKA_PASSWORD":"'"$$password_b64"'"}}' >/dev/null; echo "Kafka password synchronized to url-visit-tracker-env"

infra-ready: deploy wait-infra sync-kafka-password restart ## Wait for dependencies, synchronize credentials, and restart the app.

migration-status: ## Show migration versions recorded in the cluster database.
	$(KUBECTL) exec --namespace $(NAMESPACE) statefulset/$(POSTGRES_STATEFULSET) -- sh -ec 'export PGPASSWORD="$$(cat /opt/bitnami/postgresql/secrets/password)"; psql -h 127.0.0.1 -U url_tracker_user -d url_visit_tracker -c "SELECT app, name, applied_at FROM tortoise_migrations ORDER BY applied_at"'

status: ## Show the Helm release and application resources.
	helm list $(HELM_CONTEXT) --namespace $(NAMESPACE)
	$(KUBECTL) get deployment,statefulset,job,pods,services,pvc --namespace $(NAMESPACE) -o wide
	$(KUBECTL) get kafka,kafkauser,kafkatopic --namespace $(NAMESPACE)

logs: ## Follow application logs.
	$(KUBECTL) logs --namespace $(NAMESPACE) deployment/$(RELEASE) --all-containers=true --tail=200 --follow

port-forward: port-forward-all ## Forward the application and local development dependencies.

port-forward-app: ## Forward only the application Service to localhost.
	@echo "Application: http://localhost:$(LOCAL_PORT)"
	@echo "Metrics:     http://localhost:$(LOCAL_PORT)/metrics"
	@echo "FastAPI:     http://localhost:$(LOCAL_PORT)/docs"
	$(KUBECTL) port-forward --namespace $(NAMESPACE) service/$(RELEASE) $(LOCAL_PORT):8000

port-forward-all: ## Forward app, Postgres, Valkey, Grafana, and Prometheus; Ctrl+C stops all forwards.
	PORT_FORWARD_CONTEXT="$(PROFILE)" \
	PORT_FORWARD_NAMESPACE="$(NAMESPACE)" \
	PORT_FORWARD_MONITORING_NAMESPACE="$(MONITORING_NAMESPACE)" \
	PORT_FORWARD_RELEASE="$(RELEASE)" \
	PORT_FORWARD_GRAFANA_SERVICE="$(GRAFANA_SERVICE)" \
	PORT_FORWARD_PROMETHEUS_SERVICE="$(PROMETHEUS_SERVICE)" \
	PORT_FORWARD_APP_LOCAL_PORT="$(LOCAL_PORT)" \
	PORT_FORWARD_POSTGRES_LOCAL_PORT="$(POSTGRES_LOCAL_PORT)" \
	PORT_FORWARD_VALKEY_LOCAL_PORT="$(VALKEY_LOCAL_PORT)" \
	PORT_FORWARD_GRAFANA_LOCAL_PORT="$(GRAFANA_PORT)" \
	PORT_FORWARD_PROMETHEUS_LOCAL_PORT="$(PROMETHEUS_PORT)" \
	bash scripts/port-forward-all.sh

diagnose-port-forward: ## Inspect app pod health, endpoints, recent events, and logs after a forwarding reset.
	$(KUBECTL) get pods --namespace $(NAMESPACE) -o wide
	$(KUBECTL) get endpoints --namespace $(NAMESPACE) $(RELEASE) $(POSTGRES_STATEFULSET) $(VALKEY_DEPLOYMENT) -o wide
	$(KUBECTL) get events --namespace $(NAMESPACE) --sort-by=.lastTimestamp | tail -n 20
	-$(KUBECTL) logs --namespace $(NAMESPACE) deployment/$(RELEASE) --all-containers=true --tail=100
	-$(KUBECTL) logs --namespace $(NAMESPACE) deployment/$(RELEASE) --all-containers=true --previous --tail=100

restart: ## Restart the application Deployment.
	$(KUBECTL) rollout restart --namespace $(NAMESPACE) deployment/$(RELEASE)
	$(KUBECTL) rollout status --namespace $(NAMESPACE) deployment/$(RELEASE) --timeout=5m

uninstall: ## Uninstall the Helm release but preserve the Minikube cluster.
	-helm uninstall $(RELEASE) $(HELM_CONTEXT) --namespace $(NAMESPACE)
	-helm uninstall $(MONITORING_RELEASE) $(HELM_CONTEXT) --namespace $(MONITORING_NAMESPACE)
	-helm uninstall $(STRIMZI_RELEASE) $(HELM_CONTEXT) --namespace $(NAMESPACE)

cluster-delete: ## Delete the complete Minikube profile; requires CONFIRM=delete.
	@test "$(CONFIRM)" = "delete" || { echo "Refusing to delete the cluster. Re-run with CONFIRM=delete"; exit 1; }
	minikube delete --profile $(PROFILE)

makemigrations: ## Creates the migration files based on DB model definitions
	uv run tortoise -c app.core.config.TORTOISE_ORM makemigrations

migrate: ## Applies migrations created by the makemigrations step
	uv run tortoise -c app.core.config.TORTOISE_ORM migrate
