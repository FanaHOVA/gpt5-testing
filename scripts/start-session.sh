#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

usage() {
  echo "Usage: start-session.sh [RUN_NAME]" >&2
}

RUN_NAME_INPUT=${1:-}

SERVICE=app
HOST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_NAME=${RUN_NAME_INPUT:-$(date -u +%Y%m%d-%H%M%S)}
ARTIFACTS_HOST="${HOST_DIR}/runs/${RUN_NAME}"
mkdir -p "${ARTIFACTS_HOST}"

export RUN_NAME
export ARTIFACTS_HOST

cd "${REPO_ROOT}"
echo "Starting session: service=${SERVICE} RUN_NAME=${RUN_NAME} ARTIFACTS_HOST=${ARTIFACTS_HOST}" >&2
exec docker compose -f "${COMPOSE_FILE}" up -d "${SERVICE}"
