FROM python:3.11-slim

ARG UID=1000
ARG GID=1000
ARG USER=dev

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    build-essential \
    gcc \
    g++ \
    make \
    pkg-config \
    libssl-dev \
    locales \
    tzdata \
    tini \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user matching the host UID/GID to avoid permission issues
RUN if getent group "${GID}" >/dev/null; then :; else groupadd -g "${GID}" "${USER}"; fi \
  && useradd -m -u "${UID}" -g "${GID}" -s /bin/bash "${USER}"

# Set sane defaults
ENV PATH=/home/${USER}/.local/bin:${PATH}
ENV PIP_NO_CACHE_DIR=1

# tini ensures proper signal handling for subprocesses
ENTRYPOINT ["/usr/bin/tini", "--"]

WORKDIR /workspace

USER ${USER}

# Pre-clone smol-podcaster for immediate availability
ENV SMOL_PODCASTER_DIR=/home/${USER}/src/smol-podcaster
RUN mkdir -p /home/${USER}/src \
    && git clone --depth 1 https://github.com/FanaHOVA/smol-podcaster.git "$SMOL_PODCASTER_DIR" \
    && pip install -r "$SMOL_PODCASTER_DIR/requirements.txt"
