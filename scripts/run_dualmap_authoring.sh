#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${repo_root}" != "/app" ]]; then
    echo "Run this script inside the existing container from /app." >&2
    exit 1
fi

requested_scene="${1:-}"
layout_type="${2:-}"
if [[ -z "${requested_scene}" || -z "${layout_type}" ]]; then
    echo "Usage: $0 <scene-or-hash> <static|in_anchor|cross_anchor> [1|2|3] [val|train|minival] [--overwrite]" >&2
    exit 2
fi
shift 2

layout_index=""
split="val"
overwrite="false"
for argument in "$@"; do
    case "${argument}" in
        1|2|3)
            if [[ -n "${layout_index}" ]]; then
                echo "Only one layout index may be supplied." >&2
                exit 2
            fi
            layout_index="${argument}"
            ;;
        val|train|minival)
            split="${argument}"
            ;;
        --overwrite)
            overwrite="true"
            ;;
        *)
            echo "Unknown argument: ${argument}" >&2
            exit 2
            ;;
    esac
done

case "${layout_type}" in
    static)
        if [[ -n "${layout_index}" ]]; then
            echo "Static authoring does not accept a layout index." >&2
            exit 2
        fi
        ;;
    in_anchor|cross_anchor)
        if [[ -z "${layout_index}" ]]; then
            echo "${layout_type} requires layout index 1, 2, or 3." >&2
            exit 2
        fi
        ;;
    *)
        echo "Unsupported layout type: ${layout_type}" >&2
        exit 2
        ;;
esac

split_root="${repo_root}/data/scene_datasets/hm3d/${split}"
if [[ ! -d "${split_root}" ]]; then
    echo "HM3D split is not installed: ${split_root}" >&2
    exit 1
fi

scene_dir="${split_root}/${requested_scene}"
if [[ ! -d "${scene_dir}" ]]; then
    scene_dir="$(find "${split_root}" -mindepth 1 -maxdepth 1 -type d \
        \( -name "${requested_scene}" -o -name "*-${requested_scene}" \
        -o -name "${requested_scene}-*" \) \
        -print -quit)"
fi
if [[ -z "${scene_dir}" || ! -d "${scene_dir}" ]]; then
    echo "Scene '${requested_scene}' was not found in HM3D ${split}." >&2
    exit 1
fi

scene_mesh="$(find "${scene_dir}" -maxdepth 1 -type f \
    -name '*.basis.glb' ! -name '*.semantic.glb' -print -quit)"
dataset_config="${repo_root}/data/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json"
objects_path="${repo_root}/data/objects/ycb/configs"
scene_name="$(basename "${scene_dir}")"
output_root="${repo_root}/outputs/dualmap_authoring"
static_config="${output_root}/${scene_name}/static_scene_config.json"

if [[ -z "${scene_mesh}" || ! -f "${scene_mesh}" ]]; then
    echo "No Habitat-ready BASIS scene mesh found in ${scene_dir}." >&2
    exit 1
fi
if [[ ! -f "${dataset_config}" ]]; then
    echo "Missing HM3D dataset config: ${dataset_config}" >&2
    exit 1
fi
if [[ ! -d "${objects_path}" ]]; then
    echo "Missing YCB configs: ${objects_path}" >&2
    exit 1
fi
load_overrides=("load_from_config=false")
index_override="authoring.layout_index=null"
if [[ "${layout_type}" != "static" ]]; then
    if [[ ! -f "${static_config}" ]]; then
        echo "Create the static layout first: ${static_config}" >&2
        exit 1
    fi
    load_overrides=(
        "load_from_config=true"
        "scene_config=${static_config}"
    )
    index_override="authoring.layout_index=${layout_index}"
fi

if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is not set. Export the container's graphical display first." >&2
    exit 1
fi

cd "${repo_root}"
exec python -u -m habitat_data_collector.main \
    "scene_name=${scene_name}" \
    "scene_path=${scene_mesh}" \
    "scene_dataset_config=${dataset_config}" \
    "objects_path=${objects_path}" \
    "output_path=/app/outputs" \
    "authoring.enabled=true" \
    "authoring.output_root=${output_root}" \
    "authoring.layout_type=${layout_type}" \
    "${index_override}" \
    "authoring.overwrite=${overwrite}" \
    "${load_overrides[@]}" \
    use_ros=false \
    record_rosbag=false
