#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

usage() {
  echo "Usage: exec-in-session.sh -- <command...>" >&2
}

[[ ${1:-} == "--" ]] && shift || true
[[ $# -gt 0 ]] || { usage; echo "Missing command" >&2; exit 1; }

SERVICE=app

cd "${REPO_ROOT}"
exec docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -lc "$*"
