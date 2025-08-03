#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  # Monorepo mode (explicit target):
  run-in-docker.sh <gpt5|opus4-cc> [--no-net] [--read-only] [--artifacts <path>|--no-artifacts] [--] <command...>

  # Project-local mode (when this scripts/ folder is inside a project):
  run-in-docker.sh [--no-net] [--read-only] [--artifacts <path>|--no-artifacts] [--] <command...>

Examples:
  run-in-docker.sh gpt5 -- pytest -q
  run-in-docker.sh opus4-cc -- python -m pytest
  run-in-docker.sh gpt5 --no-net --read-only -- python -V
  run-in-docker.sh gpt5 -- bash -lc 'echo hi > "$ARTIFACTS_DIR"/hello.txt'

Flags:
  --no-net           Run with networking disabled
  --read-only        Make the container root filesystem read-only (tmpfs for /tmp and /run)
  --artifacts <path> Use a custom host path for artifacts. Relative paths are under the target folder.
  --no-artifacts     Disable the default artifacts directory for this run.

Notes:
- By default, artifacts are stored under <target>/runs/<UTC timestamp> and exposed inside the container as:
  ARTIFACTS_DIR=/artifacts, RUNS_DIR=/workspace/runs, RUN_NAME=<timestamp>, RUN_PATH=/artifacts
USAGE
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
IMAGE="selfimproving/python-dev:3.11"
DOCKERFILE="${SCRIPT_DIR}/python-dev.Dockerfile"

TARGET="${1:-}"
LOCAL_MODE=0
if [[ -z "${TARGET}" ]] || [[ "${TARGET}" != "gpt5" && "${TARGET}" != "opus4-cc" ]]; then
  LOCAL_MODE=1
else
  shift || true
fi

NO_NET=0
READ_ONLY=0
NO_ARTIFACTS=0
ARTIFACTS_PATH=""

# Parse flags until --
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-net) NO_NET=1; shift ;;
    --read-only) READ_ONLY=1; shift ;;
    --artifacts)
      shift
      ARTIFACTS_PATH="${1:-}"
      [[ -z "${ARTIFACTS_PATH}" ]] && echo "Error: --artifacts requires a path" && exit 1
      shift ;;
    --no-artifacts) NO_ARTIFACTS=1; shift ;;
    --) shift; break ;;
    -h|--help) usage; exit 0 ;;
    *) break ;;
  esac
done

[[ $# -gt 0 ]] || { echo "Error: missing command."; usage; exit 1; }

if [[ ${LOCAL_MODE} -eq 1 ]]; then
  HOST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  case "${TARGET}" in
    gpt5) HOST_DIR="${REPO_ROOT}/gpt5" ;;
    opus4-cc) HOST_DIR="${REPO_ROOT}/opus4-cc" ;;
    *) echo "Unknown target: ${TARGET}"; usage; exit 1 ;;
  esac
fi

if [[ ! -d "${HOST_DIR}" ]]; then
  echo "Missing directory: ${HOST_DIR}" >&2
  exit 2
fi

# Resolve artifacts directory
ARTIFACTS_ARGS=()
if [[ ${NO_ARTIFACTS} -eq 0 ]]; then
  if [[ -z "${ARTIFACTS_PATH}" ]]; then
    RUNS_DIR="${HOST_DIR}/runs"
    RUN_NAME=$(date -u +%Y%m%d-%H%M%S)
    ARTIFACTS_HOST="${RUNS_DIR}/${RUN_NAME}"
  else
    case "${ARTIFACTS_PATH}" in
      /*) ARTIFACTS_HOST="${ARTIFACTS_PATH}" ;;
      ~*) ARTIFACTS_HOST="${ARTIFACTS_PATH/#~/${HOME}}" ;;
      *) ARTIFACTS_HOST="${HOST_DIR}/${ARTIFACTS_PATH}" ;;
    esac
    RUNS_DIR="${HOST_DIR}/runs"
    RUN_NAME="$(basename "${ARTIFACTS_HOST}")"
  fi
  mkdir -p "${ARTIFACTS_HOST}"
  ARTIFACTS_ARGS=(
    -v "${ARTIFACTS_HOST}":/artifacts
    -e ARTIFACTS_DIR=/artifacts
    -e RUNS_DIR=/workspace/runs
    -e RUN_NAME="${RUN_NAME}"
    -e RUN_PATH=/artifacts
  )
fi

# Build the image if not present
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo "Building image ${IMAGE}..."
  docker build -f "${DOCKERFILE}" \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" \
    -t "${IMAGE}" "${REPO_ROOT}"
fi

PIP_CACHE="${HOME}/.cache/pip"
mkdir -p "${PIP_CACHE}"

NETWORK_ARGS=()
if [[ ${NO_NET} -eq 1 ]]; then
  NETWORK_ARGS+=(--network=none)
fi

FS_ARGS=()
if [[ ${READ_ONLY} -eq 1 ]]; then
  FS_ARGS+=(--read-only --tmpfs /tmp:rw,size=256m --tmpfs /run:rw,size=16m)
fi

# Run the provided command
exec docker run --rm -it \
  -v "${HOST_DIR}":/workspace \
  -v "${PIP_CACHE}":/home/dev/.cache/pip \
  -w /workspace \
  -e HOME=/home/dev \
  ${NETWORK_ARGS[@]:-} \
  ${FS_ARGS[@]:-} \
  ${ARTIFACTS_ARGS[@]:-} \
  "${IMAGE}" "$@"
