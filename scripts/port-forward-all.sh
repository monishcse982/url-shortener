#!/usr/bin/env bash

set -u

context=${PORT_FORWARD_CONTEXT:-minikube}
namespace=${PORT_FORWARD_NAMESPACE:-url-tracker}
monitoring_namespace=${PORT_FORWARD_MONITORING_NAMESPACE:-observability}
release=${PORT_FORWARD_RELEASE:-url-visit-tracker-stack}
grafana_service=${PORT_FORWARD_GRAFANA_SERVICE:-monitoring-grafana}
prometheus_service=${PORT_FORWARD_PROMETHEUS_SERVICE:-monitoring-kube-prometheus-prometheus}

app_port=${PORT_FORWARD_APP_LOCAL_PORT:-8000}
postgres_port=${PORT_FORWARD_POSTGRES_LOCAL_PORT:-5433}
valkey_port=${PORT_FORWARD_VALKEY_LOCAL_PORT:-6380}
grafana_port=${PORT_FORWARD_GRAFANA_LOCAL_PORT:-3000}
prometheus_port=${PORT_FORWARD_PROMETHEUS_LOCAL_PORT:-9090}

pids=()
labels=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${pids[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_forward() {
  local label=$1
  local ns=$2
  local service=$3
  local local_port=$4
  local remote_port=$5

  if ! kubectl --context "$context" get service "$service" --namespace "$ns" >/dev/null 2>&1; then
    echo "Missing Kubernetes Service: $service (namespace: $ns, context: $context)" >&2
    exit 1
  fi

  kubectl --context "$context" port-forward \
    --namespace "$ns" "service/$service" "$local_port:$remote_port" &
  pids+=("$!")
  labels+=("$label")
  printf '%-12s localhost:%s -> %s/%s:%s\n' \
    "$label" "$local_port" "$ns" "$service" "$remote_port"
}

echo "Starting Kubernetes port-forwards (context: $context)"
start_forward "Application" "$namespace" "$release" "$app_port" 8000
start_forward "PostgreSQL" "$namespace" "${release}-postgresql" "$postgres_port" 5432
start_forward "Valkey" "$namespace" valkey "$valkey_port" 6379
start_forward "Grafana" "$monitoring_namespace" "$grafana_service" "$grafana_port" 80
start_forward "Prometheus" "$monitoring_namespace" "$prometheus_service" "$prometheus_port" 9090

echo
echo "Application: http://localhost:$app_port/docs (metrics at /metrics)"
echo "PostgreSQL:  localhost:$postgres_port"
echo "Valkey:      localhost:$valkey_port"
echo "Grafana:     http://localhost:$grafana_port"
echo "Prometheus:  http://localhost:$prometheus_port"
echo "Press Ctrl+C to stop all forwards."

while true; do
  for index in "${!pids[@]}"; do
    pid=${pids[$index]}
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"
      status=$?
      echo "Port-forward stopped unexpectedly: ${labels[$index]} (exit $status)." >&2
      echo "For an app connection reset, run: make diagnose-port-forward" >&2
      exit "$status"
    fi
  done
  sleep 1
done
