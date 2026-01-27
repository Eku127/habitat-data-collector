"""Visualization service."""

import time
from typing import Dict, Optional, List
import cv2
import numpy as np
from PIL import Image
from habitat_sim.utils.common import d3_40_colors_rgb

from ..config.settings import (
    DEPTH_OVERLAY_SCALE,
    SEMANTIC_OVERLAY_SCALE,
    OVERLAY_START_X,
    OVERLAY_START_Y,
    OVERLAY_GAP_SIZE,
    MAP_DISPLAY_SCALE,
    COLOR_BORDER,
    COLOR_REC_ACTIVE,
    COLOR_REC_INACTIVE,
    TOPDOWN_METERS_PER_PIXEL,
)
from ..utils.topdown_map import render_topdown_map
from ..utils.coordinate_transform import CoordinateTransform


class Visualizer:
    """Service for rendering and displaying observations."""

    def __init__(self, simulator_service):
        """Initialize visualizer.
        
        Args:
            simulator_service: Simulator service instance
        """
        self.sim = simulator_service
    
    def render(self, observations: Dict, state_manager, topdown_map_img: Optional[np.ndarray] = None):
        """Render and display observations.
        
        Args:
            observations: Sensor observations
            state_manager: State manager for UI state
            topdown_map_img: Optional rendered topdown map
        """
        # Get RGB observation
        rgb_obs = observations.get("color_sensor")
        if rgb_obs is None:
            return
        
        rgb_img_cv = cv2.cvtColor(np.array(rgb_obs), cv2.COLOR_RGB2BGR)
        
        # Add depth overlay
        if "depth_sensor" in observations:
            self._add_depth_overlay(rgb_img_cv, observations["depth_sensor"])
        
        # Add semantic overlay
        if "semantic_sensor" in observations:
            self._add_semantic_overlay(rgb_img_cv, observations["semantic_sensor"])
        
        # Add topdown map
        if topdown_map_img is not None:
            self._add_topdown_map(rgb_img_cv, topdown_map_img)
        
        # Add help text
        if state_manager.app.show_help:
            self._add_help_text(rgb_img_cv)
        
        # Add recording indicator
        self._add_recording_indicator(rgb_img_cv, state_manager.app.recording)
        
        # Show window
        cv2.imshow("Habitat Data Collector", rgb_img_cv)
    
    def _add_depth_overlay(self, rgb_img: np.ndarray, depth_obs: np.ndarray):
        """Add depth overlay to RGB image."""
        depth_normalized = cv2.normalize(depth_obs, None, 0, 255, cv2.NORM_MINMAX)
        depth_img_cv = depth_normalized.astype(np.uint8)
        
        # Resize
        scale = DEPTH_OVERLAY_SCALE
        new_size = (int(rgb_img.shape[1] * scale), int(rgb_img.shape[0] * scale))
        depth_resized = cv2.resize(depth_img_cv, new_size)
        
        # Add border
        depth_bordered = cv2.copyMakeBorder(
            depth_resized, 5, 5, 5, 5,
            cv2.BORDER_CONSTANT,
            value=COLOR_BORDER
        )
        
        # Place on RGB image
        h, w = depth_bordered.shape
        y1, y2 = OVERLAY_START_Y, OVERLAY_START_Y + h
        x1, x2 = OVERLAY_START_X, OVERLAY_START_X + w
        
        if y2 <= rgb_img.shape[0] and x2 <= rgb_img.shape[1]:
            rgb_img[y1:y2, x1:x2] = cv2.cvtColor(depth_bordered, cv2.COLOR_GRAY2BGR)
    
    def _add_semantic_overlay(self, rgb_img: np.ndarray, semantic_obs: np.ndarray):
        """Add semantic overlay to RGB image."""
        # Convert semantic to colored image
        semantic_img = Image.new("P", (semantic_obs.shape[1], semantic_obs.shape[0]))
        semantic_img.putpalette(d3_40_colors_rgb.flatten())
        semantic_img.putdata((semantic_obs.flatten() % 40).astype(np.uint8))
        semantic_img = semantic_img.convert("RGB")
        semantic_img_cv = cv2.cvtColor(np.array(semantic_img), cv2.COLOR_RGB2BGR)
        
        # Resize
        scale = SEMANTIC_OVERLAY_SCALE
        new_size = (int(rgb_img.shape[1] * scale), int(rgb_img.shape[0] * scale))
        semantic_resized = cv2.resize(semantic_img_cv, new_size)
        
        # Add border
        semantic_bordered = cv2.copyMakeBorder(
            semantic_resized, 5, 5, 5, 5,
            cv2.BORDER_CONSTANT,
            value=COLOR_BORDER
        )
        
        # Calculate position (below depth)
        depth_height = int(rgb_img.shape[0] * DEPTH_OVERLAY_SCALE) + 10  # 10 = 2*5 border
        y_start = OVERLAY_START_Y + depth_height + OVERLAY_GAP_SIZE
        
        h, w, _ = semantic_bordered.shape
        y1, y2 = y_start, y_start + h
        x1, x2 = OVERLAY_START_X, OVERLAY_START_X + w
        
        if y2 <= rgb_img.shape[0] and x2 <= rgb_img.shape[1]:
            rgb_img[y1:y2, x1:x2] = semantic_bordered
    
    def _add_topdown_map(self, rgb_img: np.ndarray, topdown_map: np.ndarray):
        """Add topdown map to top-right corner."""
        map_height, map_width = topdown_map.shape[:2]
        aspect_ratio = map_width / map_height
        new_height = int(rgb_img.shape[0] * MAP_DISPLAY_SCALE)
        new_width = int(aspect_ratio * new_height)
        
        # Resize map
        map_resized = cv2.resize(topdown_map, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        # Convert to BGR if needed
        if len(map_resized.shape) == 2 or map_resized.shape[2] == 1:
            map_resized = cv2.cvtColor(map_resized, cv2.COLOR_GRAY2BGR)
        
        # Place in top-right corner
        x_start = rgb_img.shape[1] - new_width - 20
        y_start = 20
        
        h, w, _ = map_resized.shape
        y1, y2 = y_start, y_start + h
        x1, x2 = x_start, x_start + w
        
        if y2 <= rgb_img.shape[0] and x2 <= rgb_img.shape[1] and x1 >= 0:
            rgb_img[y1:y2, x1:x2] = map_resized
    
    def _add_help_text(self, rgb_img: np.ndarray):
        """Add help text overlay."""
        help_message = """
System Controls:
space:    Start/stop recording
q:        Exit and save
h:        Toggle help
m:        Toggle map

Agent Controls:
wasd:     Move/turn
arrows:   Turn/look
        """
        
        help_lines = help_message.strip().split('\n')
        
        # Calculate start position
        depth_height = int(rgb_img.shape[0] * DEPTH_OVERLAY_SCALE) + 10
        semantic_height = int(rgb_img.shape[0] * SEMANTIC_OVERLAY_SCALE) + 10
        y_start = OVERLAY_START_Y + depth_height + OVERLAY_GAP_SIZE + semantic_height + OVERLAY_GAP_SIZE
        
        for i, line in enumerate(help_lines):
            line = line.strip()
            position = (OVERLAY_START_X, y_start + i * 28)
            cv2.putText(
                rgb_img, line, position,
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 1, cv2.LINE_AA
            )
    
    def _add_recording_indicator(self, rgb_img: np.ndarray, recording: bool):
        """Add recording indicator."""
        rec_color = COLOR_REC_INACTIVE
        rec_text = "REC"
        dot_color = COLOR_REC_INACTIVE
        
        # Flashing effect when recording
        if recording:
            if int(time.time()) % 2 == 0:
                rec_color = COLOR_REC_ACTIVE
                dot_color = COLOR_REC_ACTIVE
            else:
                rec_text = ""
                dot_color = None
        
        # Position in bottom-right corner
        rec_position = (rgb_img.shape[1] - 80, rgb_img.shape[0] - 30)
        dot_position = (rgb_img.shape[1] - 93, rgb_img.shape[0] - 40)
        
        # Draw dot
        if dot_color is not None:
            cv2.circle(rgb_img, dot_position, 10, dot_color, -1)
        
        # Draw text
        cv2.putText(
            rgb_img, rec_text, rec_position,
            cv2.FONT_HERSHEY_SIMPLEX, 1, rec_color, 2, cv2.LINE_AA
        )
    
    def prepare_topdown_map(self, state_manager, object_positions: Optional[List] = None) -> Optional[np.ndarray]:
        """Prepare topdown map with annotations.
        
        Args:
            state_manager: State manager
            object_positions: Optional list of object positions in 3D
            
        Returns:
            Rendered topdown map or None
        """
        if not state_manager.app.show_map:
            return None
        
        # Get agent position in topdown coordinates
        agent_state = self.sim.get_agent_state()
        agent_position = self.sim.convert_to_topdown(agent_state.position)
        
        # Convert object positions
        topdown_object_positions = None
        if object_positions:
            topdown_object_positions = [
                self.sim.convert_to_topdown(pos)
                for pos in object_positions
            ]
        
        # Get navigation info
        nav_goal_topdown = None
        nav_path_topdown = None
        
        if state_manager.navigation.nav_goal is not None:
            nav_goal_topdown = self.sim.convert_to_topdown(state_manager.navigation.nav_goal)
        
        if state_manager.navigation.nav_path is not None:
            nav_path_topdown = [
                self.sim.convert_to_topdown(wp)
                for wp in state_manager.navigation.nav_path
            ]
        
        # Render map
        return render_topdown_map(
            self.sim.topdown_map,
            agent_position=agent_position,
            object_positions=topdown_object_positions,
            goal_position=nav_goal_topdown,
            nav_path=nav_path_topdown,
        )

