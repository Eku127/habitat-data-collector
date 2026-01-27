"""Topdown map utilities."""

import cv2
import numpy as np
from typing import List, Optional, Tuple

from ..config.settings import (
    MAP_SHRINK_ITERATIONS,
    MAP_KERNEL_SIZE,
    TOPDOWN_MAP_BORDER_SIZE,
    COLOR_AGENT,
    COLOR_OBJECT,
    COLOR_GOAL,
    COLOR_PATH,
)


def shrink_false_areas(topdown_map: np.ndarray, iterations: int = MAP_SHRINK_ITERATIONS, 
                       kernel_size: int = MAP_KERNEL_SIZE) -> np.ndarray:
    """Shrink the False (navigable) areas in the topdown map.
    
    Args:
        topdown_map: Binary image with True=obstacles, False=free space
        iterations: Number of dilation iterations
        kernel_size: Size of the dilation kernel
        
    Returns:
        Topdown map with shrunk False areas
    """
    # Convert boolean to uint8
    map_uint8 = (topdown_map * 255).astype(np.uint8)
    
    # Define kernel
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    
    # Dilate the True (obstacle) areas
    dilated_map = cv2.dilate(map_uint8, kernel, iterations=iterations)
    
    # Convert back to boolean
    shrunk_map = dilated_map > 127
    
    return shrunk_map


def check_valid_in_topdown(key_point: Tuple[float, float], topdown_map: np.ndarray) -> bool:
    """Check if a point falls in navigable area (False) of the topdown map.
    
    Args:
        key_point: Point to check (x, y)
        topdown_map: Binary map with True=obstacles, False=navigable
        
    Returns:
        True if point is in navigable area, False otherwise
    """
    height, width = topdown_map.shape
    
    x, y = int(key_point[0]), int(key_point[1])
    
    # Check bounds
    if x < 0 or y < 0 or x >= width or y >= height:
        print("Warning: Key point is out of the map range.")
        return False
    
    # Check if in navigable area (False)
    return not topdown_map[y, x]


def render_topdown_map(
    topdown_map: np.ndarray,
    agent_position: Optional[np.ndarray] = None,
    object_positions: Optional[List[np.ndarray]] = None,
    goal_position: Optional[np.ndarray] = None,
    nav_path: Optional[List[np.ndarray]] = None,
) -> np.ndarray:
    """Render a topdown map with annotations.
    
    Args:
        topdown_map: Binary topdown map
        agent_position: Agent position (x, y) in map coordinates
        object_positions: List of object positions
        goal_position: Navigation goal position
        nav_path: Navigation path points
        
    Returns:
        Rendered RGB image of the topdown map
    """
    # Convert True to gray (128), False to white (255)
    display_map = np.where(topdown_map, 128, 255).astype(np.uint8)
    
    # Draw edges
    kernel = np.ones((3, 3), np.uint8)
    dilated_map = cv2.dilate(topdown_map.astype(np.uint8), kernel, iterations=1)
    edges = dilated_map - topdown_map.astype(np.uint8)
    display_map[edges == 1] = 0
    
    # Find boundaries and crop
    coords = np.argwhere(topdown_map)
    if coords.size > 0:
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        display_map = display_map[y_min:y_max + 1, x_min:x_max + 1]
    else:
        y_min, x_min = 0, 0
    
    # Add border
    display_map = cv2.copyMakeBorder(
        display_map,
        TOPDOWN_MAP_BORDER_SIZE, TOPDOWN_MAP_BORDER_SIZE,
        TOPDOWN_MAP_BORDER_SIZE, TOPDOWN_MAP_BORDER_SIZE,
        cv2.BORDER_CONSTANT,
        value=[255, 255, 255]
    )
    
    # Convert to BGR for color annotations
    if len(display_map.shape) == 2:
        display_map = cv2.cvtColor(display_map, cv2.COLOR_GRAY2BGR)
    
    # Draw agent
    if agent_position is not None:
        agent_x = int(agent_position[0] - x_min + TOPDOWN_MAP_BORDER_SIZE)
        agent_y = int(agent_position[1] - y_min + TOPDOWN_MAP_BORDER_SIZE)
        cv2.circle(display_map, (agent_x, agent_y), 3, COLOR_AGENT, -1)
    
    # Draw objects
    if object_positions is not None:
        for obj_pos in object_positions:
            obj_x = int(obj_pos[0] - x_min + TOPDOWN_MAP_BORDER_SIZE)
            obj_y = int(obj_pos[1] - y_min + TOPDOWN_MAP_BORDER_SIZE)
            cv2.circle(display_map, (obj_x, obj_y), 3, COLOR_OBJECT, -1)
    
    # Draw goal
    if goal_position is not None:
        goal_x = int(goal_position[0] - x_min + TOPDOWN_MAP_BORDER_SIZE)
        goal_y = int(goal_position[1] - y_min + TOPDOWN_MAP_BORDER_SIZE)
        cv2.circle(display_map, (goal_x, goal_y), 3, COLOR_GOAL, -1)
    
    # Draw path
    if nav_path is not None and len(nav_path) > 1:
        for i in range(1, len(nav_path)):
            start = nav_path[i - 1]
            end = nav_path[i]
            start_x = int(start[0] - x_min + TOPDOWN_MAP_BORDER_SIZE)
            start_y = int(start[1] - y_min + TOPDOWN_MAP_BORDER_SIZE)
            end_x = int(end[0] - x_min + TOPDOWN_MAP_BORDER_SIZE)
            end_y = int(end[1] - y_min + TOPDOWN_MAP_BORDER_SIZE)
            cv2.line(display_map, (start_x, start_y), (end_x, end_y), COLOR_PATH, 1)
    
    return display_map

