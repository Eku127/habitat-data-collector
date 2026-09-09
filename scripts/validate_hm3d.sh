#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hm3d_root="${repo_root}/data/scene_datasets/hm3d"
requested_scene="${1:-}"
split="${2:-train}"
split_root="${hm3d_root}/${split}"

if [[ ! -d "${split_root}" ]]; then
    echo "HM3D ${split} is not installed. Run: scripts/download_hm3d.sh ${split}" >&2
    exit 1
fi

if [[ -z "${requested_scene}" ]]; then
    scene_dir="$(find "${split_root}" -mindepth 1 -maxdepth 1 -type d -print | sort | head -n 1)"
else
    scene_dir="${split_root}/${requested_scene}"
    if [[ ! -d "${scene_dir}" ]]; then
        scene_dir="$(find "${split_root}" -mindepth 1 -maxdepth 1 -type d \
            \( -name "${requested_scene}" -o -name "*-${requested_scene}" \) -print -quit)"
    fi
fi

if [[ -z "${scene_dir:-}" || ! -d "${scene_dir}" ]]; then
    echo "Scene '${requested_scene}' was not found in HM3D ${split}." >&2
    exit 1
fi

scene_mesh="$(find "${scene_dir}" -maxdepth 1 -type f -name '*.basis.glb' ! -name '*.semantic.glb' -print -quit)"
scene_semantic="$(find "${scene_dir}" -maxdepth 1 -type f -name '*.semantic.glb' -print -quit)"
semantic_txt="$(find "${scene_dir}" -maxdepth 1 -type f -name '*.semantic.txt' -print -quit)"
dataset_config="${hm3d_root}/hm3d_annotated_basis.scene_dataset_config.json"

for required_file in "${scene_mesh}" "${scene_semantic}" "${semantic_txt}" "${dataset_config}"; do
    if [[ -z "${required_file}" || ! -f "${required_file}" ]]; then
        echo "HM3D validation failed: a mesh, semantic annotation, or dataset config is missing." >&2
        exit 1
    fi
done

container_scene_mesh="/app/${scene_mesh#"${repo_root}/"}"
scene_name="$(basename "${scene_dir}")"

cd "${repo_root}"
docker compose -f docker/compose.yml run --rm --no-deps -T \
    --user "$(id -u):$(id -g)" \
    habitat-data-collector \
    bash -lc '
        display_number=$((($$ % 500) + 100))
        display=":${display_number}"
        socket="/tmp/.X11-unix/X${display_number}"
        log="/tmp/hdc-xvfb-${display_number}.log"

        Xvfb "${display}" -screen 0 1280x1024x24 -nolisten tcp -ac >"${log}" 2>&1 &
        xvfb_pid=$!
        trap '\''kill "${xvfb_pid}" 2>/dev/null || true'\'' EXIT

        for _ in $(seq 1 50); do
            [[ -S "${socket}" ]] && break
            if ! kill -0 "${xvfb_pid}" 2>/dev/null; then
                cat "${log}" >&2
                exit 1
            fi
            sleep 0.1
        done
        if [[ ! -S "${socket}" ]]; then
            cat "${log}" >&2
            echo "Xvfb did not become ready" >&2
            exit 1
        fi

        DISPLAY="${display}" python /app/scripts/validate_hm3d.py "$1" "$2" "$3"
    ' -- \
        "${container_scene_mesh}" \
        /app/data/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json \
        "${scene_name}"
