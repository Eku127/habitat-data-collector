"""Pure data models and validation helpers for DualMap scene authoring."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


VALID_LAYOUT_TYPES = {"static", "in_anchor", "cross_anchor"}
DUALMAP_MINIMUM_PLACED = 6


@dataclass(frozen=True)
class AuthoringTarget:
    """One keyboard-selectable rigid-object target."""

    key: int
    semantic_id: int
    handle: str


#: The eight YCB targets, and the reserved semantic IDs that identify them.
#:
#: The set is chosen so that no two members share a silhouette, because a
#: detector that cannot tell two targets apart makes the relocation queries
#: ambiguous.  Four of the original eight have been replaced:
#:
#: * ``037_scissors`` and ``025_mug`` were the two smallest objects in the set;
#:   scissors present a 1.6 cm silhouette edge-on and are missed at any useful
#:   range.  Replaced by ``006_mustard_bottle`` and ``021_bleach_cleanser``.
#: * ``029_plate`` read as a second ``024_bowl``, and ``021_bleach_cleanser``
#:   as a second ``006_mustard_bottle`` -- a flat disc and a tall bottle each
#:   appearing twice.  Replaced by ``002_master_chef_can`` and
#:   ``072-a_toy_airplane``.
#:
#: The reserved semantic IDs are deliberately unchanged, so the slot an object
#: occupies is stable even when the object is not.
DUALMAP_TARGETS = (
    AuthoringTarget(1, 50001, "003_cracker_box"),
    AuthoringTarget(2, 50002, "005_tomato_soup_can"),
    AuthoringTarget(3, 50007, "011_banana"),
    AuthoringTarget(4, 50003, "019_pitcher_base"),
    AuthoringTarget(5, 50004, "024_bowl"),
    AuthoringTarget(6, 50008, "072-a_toy_airplane"),
    AuthoringTarget(7, 50005, "002_master_chef_can"),
    AuthoringTarget(8, 50006, "006_mustard_bottle"),
)


def target_template_handles(
    available_handles: Iterable[str],
    targets: Sequence[AuthoringTarget],
) -> Dict[int, str]:
    """Resolve only configured target templates from Habitat file handles.

    Habitat returns full config paths from ``get_file_template_handles``.  The
    registered object handle is the config basename without its suffix.
    """

    handles_by_name = {
        os.path.basename(str(handle)).split(".")[0]: str(handle)
        for handle in available_handles
    }
    missing = [target.handle for target in targets if target.handle not in handles_by_name]
    if missing:
        raise ValueError(
            "Missing required authoring object templates: " + ", ".join(missing)
        )
    return {
        target.semantic_id: handles_by_name[target.handle]
        for target in targets
    }


@dataclass(frozen=True)
class AnchorInfo:
    """Identity of the semantic scene object supporting a rigid object."""

    object_id: str
    category: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AnchorInfo":
        raw_object_id = value["object_id"]
        raw_category = value["category"]
        if raw_object_id is None or raw_category is None:
            raise ValueError("Anchor fields cannot be null.")
        object_id = str(raw_object_id).strip()
        category = str(raw_category).strip()
        if not object_id or not category:
            raise ValueError("Anchor fields cannot be empty.")
        return cls(object_id=object_id, category=category)

    def to_dict(self) -> Dict[str, str]:
        return {"object_id": self.object_id, "category": self.category}


@dataclass(frozen=True)
class ObjectSnapshot:
    """Serializable rigid-object state used by the authoring undo stack."""

    semantic_id: int
    handle: str
    translation: Sequence[float]
    rotation: Sequence[float]
    anchor: Optional[AnchorInfo]


@dataclass(frozen=True)
class MutationRecord:
    """State required to undo one authoring mutation."""

    semantic_id: int
    before: Optional[ObjectSnapshot]
    was_relocated: bool


@dataclass(frozen=True)
class ValidationResult:
    """Result returned by runtime and offline authoring validators."""

    errors: Sequence[str]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def message(self) -> str:
        return "Layout is valid." if self.valid else "; ".join(self.errors)


def targets_from_config(raw_targets: Iterable[Any]) -> List[AuthoringTarget]:
    """Normalize OmegaConf/dict target entries into immutable definitions."""

    targets = [
        AuthoringTarget(
            key=int(entry["key"]),
            semantic_id=int(entry["semantic_id"]),
            handle=str(entry["handle"]),
        )
        for entry in raw_targets
    ]
    keys = [target.key for target in targets]
    semantic_ids = [target.semantic_id for target in targets]
    handles = [target.handle for target in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Authoring target keys must be unique.")
    if len(semantic_ids) != len(set(semantic_ids)):
        raise ValueError("Authoring semantic IDs must be unique.")
    if len(handles) != len(set(handles)):
        raise ValueError("Authoring target handles must be unique.")
    if sorted(keys) != list(range(1, len(targets) + 1)) or len(targets) > 9:
        raise ValueError(
            "Authoring target keys must be consecutive digits starting at 1."
        )
    return sorted(targets, key=lambda target: target.key)


def layout_output_path(
    output_root: Path,
    scene_name: str,
    layout_type: str,
    layout_index: Optional[int],
) -> Path:
    """Return the canonical output filename for an authoring slot."""

    if layout_type not in VALID_LAYOUT_TYPES:
        raise ValueError(f"Unsupported layout type: {layout_type}")
    scene_root = Path(output_root) / scene_name
    if layout_type == "static":
        if layout_index is not None:
            raise ValueError("Static layouts do not accept a layout index.")
        return scene_root / "static_scene_config.json"
    if not isinstance(layout_index, int) or layout_index < 1:
        raise ValueError("Dynamic layout index must be a positive integer.")
    return (
        scene_root
        / "dynamic_scene_config"
        / layout_type
        / f"layout_{layout_index:02d}.json"
    )


#: The dynamic layout kinds, in review order.  ``static`` is the baseline the
#: two dynamic kinds are measured against, so it always comes first.
DYNAMIC_LAYOUT_TYPES: Tuple[str, ...] = ("in_anchor", "cross_anchor")


def layout_slots(
    per_kind: int = 1,
) -> Tuple[Tuple[str, Optional[int]], ...]:
    """The layout slots of a scene: one static plus ``per_kind`` of each kind."""

    if per_kind < 1:
        raise ValueError("A scene needs at least one layout of each kind.")
    slots: List[Tuple[str, Optional[int]]] = [("static", None)]
    for layout_type in DYNAMIC_LAYOUT_TYPES:
        slots.extend((layout_type, index) for index in range(1, per_kind + 1))
    return tuple(slots)


def discover_layout_slots(
    output_root: Path,
    scene_name: str,
) -> Tuple[Tuple[str, Optional[int]], ...]:
    """The layout slots actually present for one authored scene.

    The number of dynamic layouts per kind is a property of the dataset, not of
    the code, so the review, render and verification tools read what is on disk
    instead of assuming a count.  Indices are taken in order from 01 and stop at
    the first gap, so a half-written scene reports what it really has.
    """

    scene_root = Path(output_root) / scene_name
    slots: List[Tuple[str, Optional[int]]] = []
    if (scene_root / "static_scene_config.json").is_file():
        slots.append(("static", None))
    for layout_type in DYNAMIC_LAYOUT_TYPES:
        index = 1
        while layout_output_path(output_root, scene_name, layout_type, index).is_file():
            slots.append((layout_type, index))
            index += 1
    return tuple(slots)


def slot_name(layout_type: str, layout_index: Optional[int]) -> str:
    """``("in_anchor", 2)`` -> ``"in_anchor_02"``."""

    if layout_index is None:
        return layout_type
    return f"{layout_type}_{layout_index:02d}"


def validate_authoring_layout(
    *,
    targets: Sequence[AuthoringTarget],
    object_semantic_ids: Sequence[int],
    anchors: Mapping[int, AnchorInfo],
    layout_type: str,
    baseline_anchors: Optional[Mapping[int, AnchorInfo]] = None,
    baseline_semantic_ids: Optional[Set[int]] = None,
    relocated_semantic_ids: Optional[Set[int]] = None,
    minimum_placed: int = DUALMAP_MINIMUM_PLACED,
) -> ValidationResult:
    """Validate target counts and anchor relationships for one layout.

    A static layout may use any subset of the configured target menu as long as
    it meets ``minimum_placed``.  Dynamic layouts must preserve and relocate
    exactly the subset selected by their static baseline.
    """

    errors: List[str] = []
    if layout_type not in VALID_LAYOUT_TYPES:
        return ValidationResult([f"Unsupported layout type: {layout_type}"])

    allowed = {target.semantic_id for target in targets}
    if minimum_placed < 1 or minimum_placed > len(allowed):
        return ValidationResult([
            f"minimum_placed must be between 1 and {len(allowed)}."
        ])
    counts: Dict[int, int] = {}
    for semantic_id in object_semantic_ids:
        semantic_id = int(semantic_id)
        counts[semantic_id] = counts.get(semantic_id, 0) + 1

    present = set(counts)
    configured_present = present & allowed
    unexpected = sorted(present - allowed)
    duplicates = sorted(
        semantic_id for semantic_id, count in counts.items() if count > 1
    )
    if len(configured_present) < minimum_placed:
        errors.append(
            f"At least {minimum_placed} unique configured targets are required; "
            f"found {len(configured_present)}."
        )
    if unexpected:
        errors.append(f"Unexpected target semantic IDs: {unexpected}")
    if duplicates:
        errors.append(f"Duplicate target semantic IDs: {duplicates}")

    missing_anchors = sorted(
        semantic_id
        for semantic_id in configured_present
        if semantic_id not in anchors
    )
    if missing_anchors:
        errors.append(f"Missing anchor metadata: {missing_anchors}")

    if layout_type != "static":
        baseline_anchors = baseline_anchors or {}
        baseline_ids = (
            set(baseline_semantic_ids)
            if baseline_semantic_ids is not None
            else set(baseline_anchors)
        )
        relocated_semantic_ids = relocated_semantic_ids or set()
        invalid_baseline = sorted(baseline_ids - allowed)
        if invalid_baseline:
            errors.append(
                f"Static layout has unexpected target semantic IDs: {invalid_baseline}"
            )
        if len(baseline_ids & allowed) < minimum_placed:
            errors.append(
                f"Static layout must contain at least {minimum_placed} configured "
                f"targets; found {len(baseline_ids & allowed)}."
            )

        missing_from_static = sorted(baseline_ids - configured_present)
        added_since_static = sorted(configured_present - baseline_ids)
        if missing_from_static:
            errors.append(
                f"Targets from static layout are missing: {missing_from_static}"
            )
        if added_since_static:
            errors.append(
                f"Targets not present in static layout were added: {added_since_static}"
            )

        missing_baseline = sorted(baseline_ids - baseline_anchors.keys())
        if missing_baseline:
            errors.append(f"Static layout is missing anchor metadata: {missing_baseline}")

        not_relocated = sorted(baseline_ids - set(relocated_semantic_ids))
        if not_relocated:
            errors.append(f"Targets not relocated in this session: {not_relocated}")
        unexpected_relocated = sorted(set(relocated_semantic_ids) - baseline_ids)
        if unexpected_relocated:
            errors.append(
                "Relocated target IDs are not in the static layout: "
                f"{unexpected_relocated}"
            )

        for semantic_id in sorted(baseline_ids):
            current = anchors.get(semantic_id)
            baseline = baseline_anchors.get(semantic_id)
            if current is None or baseline is None:
                continue
            same_anchor = current.object_id == baseline.object_id
            if layout_type == "in_anchor" and not same_anchor:
                errors.append(
                    f"Target {semantic_id} moved to a different anchor "
                    f"({baseline.object_id} -> {current.object_id})."
                )
            if layout_type == "cross_anchor" and same_anchor:
                errors.append(
                    f"Target {semantic_id} is still on static anchor {current.object_id}."
                )

    return ValidationResult(errors)


def validate_saved_config(
    data: Mapping[str, Any],
    targets: Sequence[AuthoringTarget],
    *,
    expected_layout_type: Optional[str] = None,
    expected_layout_index: Optional[int] = None,
    baseline_data: Optional[Mapping[str, Any]] = None,
    require_existing_paths: bool = False,
    minimum_placed: int = DUALMAP_MINIMUM_PLACED,
) -> ValidationResult:
    """Validate one serialized authoring configuration."""

    if not isinstance(data, Mapping):
        return ValidationResult(["Top-level JSON value must be an object."])

    errors: List[str] = []
    expected_mapping = {
        target.semantic_id: target.handle for target in targets
    }
    raw_mapping = data.get("id_handle_mapping", {})
    try:
        if not isinstance(raw_mapping, Mapping):
            raise TypeError
        actual_mapping = {
            int(key): str(value)
            for key, value in raw_mapping.items()
        }
    except (TypeError, ValueError):
        actual_mapping = {}
    if actual_mapping != expected_mapping:
        errors.append("id_handle_mapping does not match the configured target menu.")

    authoring = data.get("authoring", {})
    if not isinstance(authoring, Mapping):
        errors.append("authoring must be an object.")
        authoring = {}
    layout_type = authoring.get("layout_type")
    layout_index = authoring.get("layout_index")
    if expected_layout_type is not None and layout_type != expected_layout_type:
        errors.append(
            f"Expected layout type {expected_layout_type}, found {layout_type}."
        )
    if expected_layout_index is not None and layout_index != expected_layout_index:
        errors.append(
            f"Expected layout index {expected_layout_index}, found {layout_index}."
        )

    objects = data.get("objects", [])
    if not isinstance(objects, list):
        errors.append("objects must be an array.")
        objects = []
    object_semantic_ids: List[int] = []
    anchors: Dict[int, AnchorInfo] = {}
    for index, obj in enumerate(objects):
        if not isinstance(obj, Mapping):
            errors.append(f"Object {index} must be an object.")
            continue
        try:
            semantic_id = int(obj["semantic_id"])
            object_semantic_ids.append(semantic_id)
        except (KeyError, TypeError, ValueError):
            errors.append(f"Object {index} has an invalid semantic_id.")
            continue
        anchor = obj.get("anchor")
        if isinstance(anchor, Mapping):
            try:
                anchors[semantic_id] = AnchorInfo.from_mapping(anchor)
            except (KeyError, TypeError, ValueError):
                errors.append(f"Object {semantic_id} has invalid anchor metadata.")
        translation = obj.get("translation")
        if not isinstance(translation, list) or len(translation) != 3:
            errors.append(f"Object {semantic_id} has an invalid translation.")
        else:
            try:
                if not all(math.isfinite(float(value)) for value in translation):
                    errors.append(f"Object {semantic_id} has an invalid translation.")
            except (TypeError, ValueError):
                errors.append(f"Object {semantic_id} has an invalid translation.")
        rotation = obj.get("rotation")
        if not isinstance(rotation, list) or len(rotation) != 4:
            errors.append(f"Object {semantic_id} has an invalid quaternion.")
        else:
            try:
                values = [float(value) for value in rotation]
                norm = math.sqrt(sum(value ** 2 for value in values))
                if not all(math.isfinite(value) for value in values):
                    errors.append(f"Object {semantic_id} has an invalid quaternion.")
                elif abs(norm - 1.0) > 1e-3:
                    errors.append(
                        f"Object {semantic_id} quaternion norm is {norm:.6f}, not 1."
                    )
            except (TypeError, ValueError):
                errors.append(f"Object {semantic_id} has an invalid quaternion.")

    baseline_anchors: Dict[int, AnchorInfo] = {}
    baseline_semantic_ids: Set[int] = set()
    if baseline_data is not None:
        baseline_objects = baseline_data.get("objects", [])
        if not isinstance(baseline_objects, list):
            baseline_objects = []
        for obj in baseline_objects:
            if not isinstance(obj, Mapping):
                continue
            try:
                semantic_id = int(obj["semantic_id"])
                baseline_semantic_ids.add(semantic_id)
            except (KeyError, TypeError, ValueError):
                continue
            anchor = obj.get("anchor")
            if not isinstance(anchor, Mapping):
                continue
            try:
                baseline_anchors[semantic_id] = AnchorInfo.from_mapping(anchor)
            except (KeyError, TypeError, ValueError):
                continue

    relocated_values = authoring.get("relocated_semantic_ids", [])
    relocated: Set[int] = set()
    if not isinstance(relocated_values, list):
        errors.append("authoring.relocated_semantic_ids must be an array.")
    else:
        try:
            relocated = {int(value) for value in relocated_values}
        except (TypeError, ValueError):
            errors.append("authoring.relocated_semantic_ids contains an invalid ID.")
    runtime_result = validate_authoring_layout(
        targets=targets,
        object_semantic_ids=object_semantic_ids,
        anchors=anchors,
        layout_type=str(layout_type),
        baseline_anchors=baseline_anchors,
        baseline_semantic_ids=(
            baseline_semantic_ids if baseline_data is not None else None
        ),
        relocated_semantic_ids=relocated,
        minimum_placed=minimum_placed,
    )
    errors.extend(runtime_result.errors)

    scene = data.get("scene", {})
    if not isinstance(scene, Mapping):
        errors.append("scene must be an object.")
        scene = {}
    for key in ("scene_path", "scene_dataset_config"):
        value = scene.get(key)
        if not value:
            errors.append(f"scene.{key} is missing.")
        elif require_existing_paths and not Path(value).is_file():
            errors.append(f"scene.{key} does not exist: {value}")

    return ValidationResult(errors)
