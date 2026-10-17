#!/usr/bin/env bash

set -u

context=${PORT_FORWARD_CONTEXT:-minikube}
namespace=${PORT_FORWARD_NAMESPACE:-shawty}
monitoring_namespace=${PORT_FORWARD_MONITORING_NAMESPACE:-observability}
release=${PORT_FORWARD_RELEASE:-shawty-stack}
frontend_service=${PORT_FORWARD_FRONTEND_SERVICE:-${release}-ui}
grafana_service=${PORT_FORWARD_GRAFANA_SERVICE:-monitoring-grafana}
prometheus_service=${PORT_FORWARD_PROMETHEUS_SERVICE:-monitoring-kube-prometheus-prometheus}

app_port=${PORT_FORWARD_APP_LOCAL_PORT:-8000}
postgres_port=${PORT_FORWARD_POSTGRES_LOCAL_PORT:-5433}
valkey_port=${PORT_FORWARD_VALKEY_LOCAL_PORT:-6380}
grafana_port=${PORT_FORWARD_GRAFANA_LOCAL_PORT:-3000}
prometheus_port=${PORT_FORWARD_PROMETHEUS_LOCAL_PORT:-9090}
frontend_port=${PORT_FORWARD_FRONTEND_LOCAL_PORT:-5173}

pids=()
labels=()
required_forwards=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do
    if [[ $pid != 0 ]]; then kill "$pid" 2>/dev/null || true; fi
  done
  for pid in "${pids[@]}"; do
    if [[ $pid != 0 ]]; then wait "$pid" 2>/dev/null || true; fi
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
  local required=$6

  if ! kubectl --context "$context" get service "$service" --namespace "$ns" >/dev/null 2>&1; then
    echo "Missing Kubernetes Service: $service (namespace: $ns, context: $context)" >&2
    if [[ $required == 1 ]]; then exit 1; fi
    return
  fi

  kubectl --context "$context" port-forward \
    --namespace "$ns" "service/$service" "$local_port:$remote_port" &
  pids+=("$!")
  labels+=("$label")
  required_forwards+=("$required")
  printf '%-12s localhost:%s -> %s/%s:%s\n' \
    "$label" "$local_port" "$ns" "$service" "$remote_port"
}

echo "Starting Kubernetes port-forwards (context: $context)"
start_forward "Application" "$namespace" "$release" "$app_port" 8000 1
if [[ ${PORT_FORWARD_FRONTEND:-0} == 1 ]]; then
  start_forward "Shawty UI" "$namespace" "$frontend_service" "$frontend_port" 8080 1
fi
if [[ ${PORT_FORWARD_CORE_ONLY:-0} != 1 ]]; then
  start_forward "PostgreSQL" "$namespace" "${release}-postgresql" "$postgres_port" 5432 0
  start_forward "Valkey" "$namespace" valkey "$valkey_port" 6379 0
  start_forward "Grafana" "$monitoring_namespace" "$grafana_service" "$grafana_port" 80 0
  start_forward "Prometheus" "$monitoring_namespace" "$prometheus_service" "$prometheus_port" 9090 0
fi

echo
echo "Application: http://localhost:$app_port/docs (metrics at /metrics)"
if [[ ${PORT_FORWARD_CORE_ONLY:-0} != 1 ]]; then
  echo "PostgreSQL:  localhost:$postgres_port"
  echo "Valkey:      localhost:$valkey_port"
  echo "Grafana:     http://localhost:$grafana_port"
  echo "Prometheus:  http://localhost:$prometheus_port"
fi
if [[ ${PORT_FORWARD_FRONTEND:-0} == 1 ]]; then
  echo "Shawty UI:   http://localhost:$frontend_port"
fi
echo "Press Ctrl+C to stop the local forwards."

while true; do
  for index in "${!pids[@]}"; do
    pid=${pids[$index]}
    if [[ $pid == 0 ]]; then continue; fi
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"
      status=$?
      echo "Port-forward stopped unexpectedly: ${labels[$index]} (exit $status)." >&2
      if [[ ${required_forwards[$index]} == 1 ]]; then
        echo "Run make diagnose-port-forward to inspect the app connection." >&2
        exit 1
      fi
      pids[$index]=0
      echo "The API and UI forwards remain active." >&2
    fi
  done
  sleep 1
done
