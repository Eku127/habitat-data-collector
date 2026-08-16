#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hm3d_root="${repo_root}/data/scene_datasets/hm3d"
split="${1:-train}"

case "${split}" in
    train|val|minival) ;;
    *)
        echo "Usage: $0 [train|val|minival]" >&2
        exit 2
        ;;
esac

if [[ ! -d "${hm3d_root}/${split}" ]]; then
    echo "HM3D ${split} is not installed. Run: scripts/download_hm3d.sh ${split}" >&2
    exit 1
fi

find "${hm3d_root}/${split}" -mindepth 1 -maxdepth 1 -type d \
    -printf '%f\n' | sort

