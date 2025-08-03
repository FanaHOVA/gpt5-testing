## Running isolated commands in Docker

This directory contains wrappers to run commands in containers for `gpt5` and `opus4-cc`.

### One-off runs (ephemeral)
Use the single-run wrapper when you want strict isolation per command:
```bash
./scripts/run-in-docker.sh gpt5 -- python -V
./scripts/run-in-docker.sh opus4-cc -- bash -lc 'pip install -U pip && pip install pytest && pytest -q'
```
- Isolation toggles: `--no-net`, `--read-only`
- Artifacts: default to `<target>/runs/<UTC timestamp>` and are available as `/artifacts` inside the container. Use `--artifacts <path>` or `--no-artifacts` to customize.
- Preinstalled repo: `SMOL_PODCASTER_DIR=/home/dev/src/smol-podcaster` (https://github.com/FanaHOVA/smol-podcaster.git)

### Long-running sessions (docker compose)
For multi-command or long-running tasks, start a persistent container and exec into it. These scripts are project-local: copy the whole `scripts/` folder into your project and run from there.
```bash
# From within your project (scripts is at ./scripts)
./scripts/start-session.sh             # starts service `app`, creates ./runs/<timestamp>
./scripts/exec-in-session.sh -- python -V
./scripts/exec-in-session.sh -- bash -lc 'echo hello > "$ARTIFACTS_DIR"/hello.txt'
./scripts/stop-session.sh --rm
```
- Inside the session, useful env vars:
  - `ARTIFACTS_DIR` points to the host-mounted artifacts directory
  - `RUN_NAME` is the UTC timestamp used for the run folder
  - `SMOL_PODCASTER_DIR` points to the pre-cloned repo in the image

Compose file: `scripts/docker-compose.yml`
- Service: `app`
- Volumes: project root mounted at `/workspace`, pip cache persisted, artifacts mount at `/artifacts`

### Rebuild the image
```bash
docker rmi selfimproving/python-dev:3.11
./scripts/run-in-docker.sh gpt5 -- python -V  # triggers rebuild
```

### Notes
- Both wrappers run as a non-root user mapped to your host UID/GID to avoid root-owned files.
- For stricter isolation in sessions, you can edit `docker-compose.yml` to add `read_only: true` or `network_mode: none` on a service.
