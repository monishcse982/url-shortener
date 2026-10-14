#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PRESETS_DIR="$SCRIPT_DIR/presets"
REPORTS_DIR="$PROJECT_DIR/reports/load"

list_presets() {
  find "$PRESETS_DIR" -maxdepth 1 -name "*.env" -type f \
    | sed "s#^$PRESETS_DIR/##; s#\\.env\$##" \
    | sort
}

usage() {
  echo "Usage: $0 <preset-name> [--base-url URL] | --list"
  echo
  echo "Options:"
  echo "  --base-url URL  API base URL (default: http://localhost:8080)"
  echo
  echo "Available presets:"
  list_presets | sed "s/^/  /"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "--list" || "$1" == "-l" || "$1" == "list" ]]; then
  if [[ $# -ne 1 ]]; then
    usage
    exit 1
  fi
  list_presets
  exit 0
fi

PRESET_NAME="${1%.env}"
shift

BASE_URL_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "Error: --base-url requires a URL" >&2
        usage
        exit 1
      fi
      BASE_URL_OVERRIDE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

PRESET_FILE="$PRESETS_DIR/$PRESET_NAME.env"

if [[ ! -f "$PRESET_FILE" ]]; then
  echo "Unknown preset: $PRESET_NAME" >&2
  echo
  usage
  exit 1
fi

set -a
source "$PRESET_FILE"
set +a

BASE_URL="${BASE_URL_OVERRIDE:-${BASE_URL:-http://localhost:8080}}"
while [[ "$BASE_URL" == */ ]]; do
  BASE_URL="${BASE_URL%/}"
done

if [[ ! "$BASE_URL" =~ ^https?://[^/]+$ ]]; then
  echo "Invalid base URL: $BASE_URL (expected http://host[:port] or https://host[:port])" >&2
  exit 1
fi

: "${SCENARIO_FILE:?SCENARIO_FILE is required in $PRESET_FILE}"
: "${PATTERN_FILE:?PATTERN_FILE is required in $PRESET_FILE}"

SCENARIO_PATH="$SCRIPT_DIR/scenarios/$SCENARIO_FILE"
PATTERN_PATH="$SCRIPT_DIR/patterns/$PATTERN_FILE"

if [[ ! -f "$SCENARIO_PATH" ]]; then
  echo "Scenario file not found: $SCENARIO_PATH" >&2
  exit 1
fi

if [[ ! -f "$PATTERN_PATH" ]]; then
  echo "Pattern file not found: $PATTERN_PATH" >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$REPORTS_DIR/$PRESET_NAME/$TIMESTAMP"
mkdir -p "$RUN_DIR"

COMMAND=(
  uv run locust
  -f "$SCENARIO_PATH,$PATTERN_PATH,$SCRIPT_DIR/patterns/_options.py"
  --host "$BASE_URL"
  --headless
  --csv "$RUN_DIR/locust"
  --csv-full-history
  --html "$RUN_DIR/report.html"
  --logfile "$RUN_DIR/locust.log"
  --loglevel "${LOG_LEVEL:-INFO}"
)

add_arg() {
  local env_name="$1"
  local cli_name="$2"
  local value="${!env_name:-}"

  if [[ -n "$value" ]]; then
    COMMAND+=("$cli_name" "$value")
  fi
}

add_arg PATTERN_DURATION_SECONDS --pattern-duration-seconds
add_arg PATTERN_SPAWN_RATE --pattern-spawn-rate
add_arg TARGET_USERS --target-users
add_arg RAMP_DURATION_SECONDS --ramp-duration-seconds
add_arg CONSTANT_USERS --constant-users
add_arg CONCURRENT_USERS --concurrent-users
add_arg SPIKE_USERS --spike-users
add_arg SPIKE_DURATION_SECONDS --spike-duration-seconds
add_arg SPIKE_FREQUENCY_SECONDS --spike-frequency-seconds
add_arg JITTER_SECONDS --jitter-seconds
add_arg INITIAL_DELAY_SECONDS --initial-delay-seconds
add_arg STEP_DURATION_SECONDS --step-duration-seconds
add_arg STEP_USERS --step-users
add_arg MAX_USERS --max-users
add_arg TARGET_RPS --target-rps
add_arg ESTIMATED_RPS_PER_USER --estimated-rps-per-user

cp "$PRESET_FILE" "$RUN_DIR/preset.env"
printf "%q " "${COMMAND[@]}" > "$RUN_DIR/command.txt"
printf "\n" >> "$RUN_DIR/command.txt"

echo "Preset: $PRESET_NAME"
echo "Base URL: $BASE_URL"
echo "Scenario: $SCENARIO_FILE"
echo "Pattern: $PATTERN_FILE"
echo "Reports: $RUN_DIR"
echo
echo "Starting Locust..."

cd "$PROJECT_DIR"
"${COMMAND[@]}"

echo
echo "Load test complete."
echo "HTML report: $RUN_DIR/report.html"
echo "CSV prefix: $RUN_DIR/locust"
echo "Logs: $RUN_DIR/locust.log"
