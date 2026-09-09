#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${repo_root}/docker/compose.yml"
hm3d_root="${repo_root}/data/scene_datasets/hm3d"
split="${2:-train}"
requested_scene="${1:-}"

case "${split}" in
    train|val|minival) ;;
    *)
        echo "Usage: $0 [SCENE_FOLDER_OR_HASH] [train|val|minival]" >&2
        exit 2
        ;;
esac

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
    echo "Available scenes: scripts/list_hm3d_scenes.sh ${split}" >&2
    exit 1
fi

scene_mesh="$(find "${scene_dir}" -maxdepth 1 -type f -name '*.basis.glb' ! -name '*.semantic.glb' -print -quit)"
dataset_config="${hm3d_root}/hm3d_annotated_basis.scene_dataset_config.json"
objects_path="${repo_root}/data/objects/ycb/configs"

if [[ -z "${scene_mesh}" ]]; then
    echo "No Habitat-ready *.basis.glb mesh found in ${scene_dir}" >&2
    exit 1
fi
if [[ ! -f "${dataset_config}" ]]; then
    echo "Missing semantic dataset config: ${dataset_config}" >&2
    exit 1
fi

scene_name="$(basename "${scene_dir}")"
container_scene_mesh="/app/${scene_mesh#"${repo_root}/"}"

if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is not set; run this launcher from a graphical desktop terminal." >&2
    echo "For a non-interactive installation check, run scripts/validate_hm3d.sh ${scene_name} ${split}" >&2
    exit 1
fi

cd "${repo_root}"
docker compose -f "${compose_file}" run --rm --no-deps \
    --user "$(id -u):$(id -g)" \
    -e DISPLAY \
    habitat-data-collector \
    python -u -m habitat_data_collector.main \
        "scene_name=${scene_name}" \
        "scene_path=${container_scene_mesh}" \
        "scene_dataset_config=/app/data/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json" \
        "objects_path=/app/${objects_path#"${repo_root}/"}" \
        "output_path=/app/outputs" \
        use_ros=false \
        record_rosbag=false
