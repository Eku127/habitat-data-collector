"""State management for the application."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import habitat_sim


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


class StateManager:
    """Centralized state manager for the application."""

    def __init__(self):
        self.app = AppState()
        self.recording = RecordingState()
        self.navigation = NavigationState()
        self.objects = ObjectState()
        
        # Counters
        self.help_count = 0
        self.map_count = 0

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

