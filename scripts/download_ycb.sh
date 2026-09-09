#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${repo_root}/docker/compose.yml"

mkdir -p "${repo_root}/data"

cd "${repo_root}"
docker compose -f "${compose_file}" run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" \
    habitat-data-collector \
    python -m habitat_sim.utils.datasets_download \
        --uids ycb \
        --data-path /app/data \
        --no-replace

# Keep the downloader-created link valid on both the host and in /app.
ln -sfn ../versioned_data/ycb "${repo_root}/data/objects/ycb"

