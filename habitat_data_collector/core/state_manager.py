"""State management for the application."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
import habitat_sim

from ..authoring import (
    AnchorInfo,
    AuthoringTarget,
    DUALMAP_MINIMUM_PLACED,
    MutationRecord,
    targets_from_config,
)


@dataclass
class ActionRecord:
    """Record of a single action."""
    action: Optional[str]
    timestamp: float
    # For object manipulation actions
    object_id: Optional[int] = None
    semantic_id: Optional[int] = None
    translation: Optional[List[float]] = None
    rotation: Optional[List[float]] = None


@dataclass
class AppState:
    """Main application state."""
    recording: bool = False
    is_navigating: bool = False
    show_map: bool = False
    show_help: bool = False
    running: bool = True


@dataclass
class RecordingState:
    """Recording-related state."""
    actions: List[ActionRecord] = field(default_factory=list)
    all_actions: List[ActionRecord] = field(default_factory=list)
    init_state: Optional[habitat_sim.AgentState] = None
    init_time: Optional[float] = None
    rosbag_process: Optional[Any] = None


@dataclass
class NavigationState:
    """Navigation-related state."""
    nav_goal: Optional[Any] = None
    nav_path: Optional[List] = None
    continuous_path_follower: Optional[Any] = None
    previous_global_path: Optional[List] = None


@dataclass
class ObjectState:
    """Object manipulation state."""
    all_rigid_objects: List = field(default_factory=list)
    grabbed_object_semantic_id: Optional[int] = None
    id_handle_dict: Dict[int, str] = field(default_factory=dict)
    all_bboxes_for_place: List = field(default_factory=list)


@dataclass
class AuthoringState:
    """Interactive state for deterministic DualMap layout authoring."""

    enabled: bool = False
    targets: List[AuthoringTarget] = field(default_factory=list)
    selected_index: int = 0
    minimum_placed: int = DUALMAP_MINIMUM_PLACED
    layout_type: str = "static"
    layout_index: Optional[int] = None
    anchors: Dict[int, AnchorInfo] = field(default_factory=dict)
    baseline_anchors: Dict[int, AnchorInfo] = field(default_factory=dict)
    baseline_semantic_ids: Set[int] = field(default_factory=set)
    relocated_semantic_ids: Set[int] = field(default_factory=set)
    history: List[MutationRecord] = field(default_factory=list)
    last_status: str = "Select a target with keys 1-8."
    last_status_ok: Optional[bool] = None

    @property
    def selected_target(self) -> Optional[AuthoringTarget]:
        if not self.targets:
            return None
        return self.targets[self.selected_index]


class StateManager:
    """Centralized state manager for the application."""

    def __init__(self):
        self.app = AppState()
        self.recording = RecordingState()
        self.navigation = NavigationState()
        self.objects = ObjectState()
        self.authoring = AuthoringState()
        
        # Counters
        self.help_count = 0
        self.map_count = 0

    def configure_authoring(self, authoring_cfg: Any):
        """Initialize authoring state from the resolved application config."""
        if not authoring_cfg or not bool(authoring_cfg.get("enabled", False)):
            return
        self.authoring.enabled = True
        self.authoring.targets = targets_from_config(authoring_cfg.targets)
        self.authoring.minimum_placed = int(
            authoring_cfg.get("minimum_placed", DUALMAP_MINIMUM_PLACED)
        )
        if not 1 <= self.authoring.minimum_placed <= len(self.authoring.targets):
            raise ValueError(
                "authoring.minimum_placed must be between 1 and the number "
                "of configured targets."
            )
        self.authoring.layout_type = str(authoring_cfg.layout_type)
        raw_index = authoring_cfg.get("layout_index")
        self.authoring.layout_index = None if raw_index is None else int(raw_index)

    def toggle_recording(self):
        """Toggle recording state."""
        self.app.recording = not self.app.recording
        
    def toggle_map(self):
        """Toggle map display."""
        self.map_count += 1
        self.app.show_map = (self.map_count % 2 == 1)
        
    def toggle_help(self):
        """Toggle help display."""
        self.help_count += 1
        self.app.show_help = (self.help_count % 2 == 1)
        
    def toggle_navigation(self):
        """Toggle navigation mode."""
        self.app.is_navigating = not self.app.is_navigating
        
    def stop(self):
        """Stop the application."""
        self.app.running = False
