#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${repo_root}/docker/compose.yml"
env_file="${HDC_ENV_FILE:-${repo_root}/.env}"

if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
fi

: "${MATTERPORT_TOKEN_ID:?Set MATTERPORT_TOKEN_ID in ${env_file} or the environment}"
: "${MATTERPORT_TOKEN_SECRET:?Set MATTERPORT_TOKEN_SECRET in ${env_file} or the environment}"

if [[ "$#" -eq 0 ]]; then
    set -- train val
fi

uids=()
for split in "$@"; do
    case "${split}" in
        train|val|minival)
            uids+=("hm3d_${split}_v0.2")
            ;;
        all)
            uids+=("hm3d")
            ;;
        hm3d_*)
            uids+=("${split}")
            ;;
        *)
            echo "Unknown HM3D split or uid: ${split}" >&2
            echo "Usage: $0 [train] [val] [minival] [all]" >&2
            exit 2
            ;;
    esac
done

mkdir -p "${repo_root}/data"

echo "Downloading ${uids[*]} to ${repo_root}/data"
echo "The Habitat-ready BASIS meshes and semantic annotations will be installed."

cd "${repo_root}"
docker compose -f "${compose_file}" run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" \
    -e MATTERPORT_TOKEN_ID \
    -e MATTERPORT_TOKEN_SECRET \
    habitat-data-collector \
    bash -lc 'python -m habitat_sim.utils.datasets_download \
        --username "$MATTERPORT_TOKEN_ID" \
        --password "$MATTERPORT_TOKEN_SECRET" \
        --uids "$@" \
        --data-path /app/data \
        --no-replace' -- "${uids[@]}"

# The upstream downloader creates an absolute /app symlink. A relative link
# works both on the host and in the /app-mounted container.
ln -sfn ../versioned_data/hm3d-0.2/hm3d \
    "${repo_root}/data/scene_datasets/hm3d"
