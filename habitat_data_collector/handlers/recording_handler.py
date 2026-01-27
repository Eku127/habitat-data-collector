"""Recording and playback handler."""

import time
import subprocess
from pathlib import Path

from .base_handler import BaseHandler
from ..core.event_dispatcher import Event, EventType, ActionEvent
from ..core.state_manager import ActionRecord


class RecordingHandler(BaseHandler):
    """Handler for recording and playback."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Subscribe to events
        self.events.subscribe(EventType.RECORDING_START, self.handle_start_recording)
        self.events.subscribe(EventType.RECORDING_STOP, self.handle_stop_recording)
        self.events.subscribe(EventType.ACTION_MOVE, self.handle_action)
        self.events.subscribe(EventType.ACTION_TURN, self.handle_action)
        self.events.subscribe(EventType.ACTION_LOOK, self.handle_action)
    
    def handle_start_recording(self, event: Event):
        """Handle recording start."""
        if self.state.app.recording:
            return  # Already recording
        
        print(f"Recording started (save_mode: {self.sim.cfg.get('save_mode', 'timestamp')})")
        save_mode = self.sim.cfg.get('save_mode', 'timestamp')
        if save_mode == "action":
            print("  -> Only frames with actual actions will be saved")
        else:
            print("  -> All frames (including idle) will be saved")
        
        self.state.app.recording = True
        self.state.recording.init_state = self.sim.get_agent_state()
        self.state.recording.init_time = time.time()
        self.state.recording.actions = []
        
        # Start ROS bag if enabled
        if self.sim.cfg.get("record_rosbag", False):
            from ..utils.ros_utils import start_rosbag_recording
            scene_dir = Path(self.sim.cfg.output_path) / self.sim.cfg.dataset_name / self.sim.cfg.scene_name
            rosbag_output_path = scene_dir / "rosbag2"
            print(f"Start ROS bag recording: {rosbag_output_path}")
            self.state.recording.rosbag_process = start_rosbag_recording(rosbag_output_path)
    
    def handle_stop_recording(self, event: Event):
        """Handle recording stop."""
        if not self.state.app.recording:
            return  # Not recording
        
        print("Recording stopped")
        self.state.app.recording = False
        self.state.recording.all_actions.extend(self.state.recording.actions)
        
        # Stop ROS bag if running
        if self.state.recording.rosbag_process is not None:
            from ..utils.ros_utils import stop_rosbag_recording
            stop_rosbag_recording(self.state.recording.rosbag_process)
            self.state.recording.rosbag_process = None
    
    def handle_action(self, event: ActionEvent):
        """Handle action during recording."""
        if not self.state.app.recording:
            return
        
        action_record = ActionRecord(
            action=event.action,
            timestamp=event.timestamp
        )
        self.state.recording.actions.append(action_record)
    
    def handle_no_action(self, timestamp: float):
        """Handle idle frame during recording (timestamp mode only)."""
        if not self.state.app.recording:
            return
        
        save_mode = self.sim.cfg.get('save_mode', 'timestamp')
        if save_mode == "timestamp":
            action_record = ActionRecord(
                action=None,
                timestamp=timestamp
            )
            self.state.recording.actions.append(action_record)
    
    def add_object_action(self, action: str, obj, timestamp: float):
        """Add object manipulation action to recording.
        
        Args:
            action: Action name (add_object, remove_object, place_in_view)
            obj: The manipulated object
            timestamp: Action timestamp
        """
        if not self.state.app.recording:
            return
        
        if obj is not None:
            translation_list = [obj.translation.x, obj.translation.y, obj.translation.z]
            rotation_list = [
                obj.rotation.vector.x, 
                obj.rotation.vector.y, 
                obj.rotation.vector.z, 
                obj.rotation.scalar
            ]
            
            action_record = ActionRecord(
                action=action,
                timestamp=timestamp,
                object_id=obj.object_id,
                semantic_id=obj.semantic_id,
                translation=translation_list,
                rotation=rotation_list
            )
        else:
            action_record = ActionRecord(
                action=action,
                timestamp=timestamp,
                object_id=None,
                semantic_id=None,
                translation=None,
                rotation=None
            )
        
        self.state.recording.actions.append(action_record)

