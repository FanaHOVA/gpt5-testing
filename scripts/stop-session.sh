#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

usage() {
  echo "Usage: stop-session.sh [--rm]" >&2
}

REMOVE=0
[[ ${1:-} == "--rm" ]] && REMOVE=1

SERVICE=app

cd "${REPO_ROOT}"
docker compose -f "${COMPOSE_FILE}" stop "${SERVICE}"
if [[ ${REMOVE} -eq 1 ]]; then
  docker compose -f "${COMPOSE_FILE}" rm -f "${SERVICE}"
fi
