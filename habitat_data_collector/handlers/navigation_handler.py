"""Navigation handler."""

import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Optional, List
import habitat_sim
from habitat_sim.utils import common as utils
import magnum as mn

from .base_handler import BaseHandler
from ..core.event_dispatcher import Event, EventType
from ..config.settings import (
    WAYPOINT_THRESHOLD,
    PATH_FILTER_TOLERANCE,
    ANGULAR_ERROR_THRESHOLD,
    MAX_LINEAR_SPEED,
    MAX_TURN_SPEED,
    PATH_FOLLOWER_STEP_SIZE,
)


class ContinuousPathFollower:
    """Continuous path follower for navigation."""
    
    def __init__(self, sim, path_points: List, agent_state, waypoint_threshold: float):
        self._sim = sim
        self._points = path_points
        assert len(self._points) > 0
        
        self._length = self._calculate_cumulative_distance()
        self._agent_state = agent_state
        self._threshold = waypoint_threshold
        self._step_size = PATH_FOLLOWER_STEP_SIZE
        self.progress = 0.0
        self.waypoint = path_points[0]
        
        self.vel_control = habitat_sim.physics.VelocityControl()
        self._point_progress, self._segment_tangents = self._setup_progress_tangents()
        
        self.vel_control.controlling_lin_vel = True
        self.vel_control.lin_vel_is_local = True
        self.vel_control.controlling_ang_vel = True
        self.vel_control.ang_vel_is_local = True
        
        print(f"Path follower initialized: length={self._length:.2f}, points={len(self._points)}")
    
    def _calculate_cumulative_distance(self) -> float:
        """Calculate total path length."""
        cumulative_distance = 0.0
        for i in range(1, len(self._points)):
            point_a = self._points[i-1]
            point_b = self._points[i]
            distance = np.linalg.norm(np.array(point_b) - np.array(point_a))
            cumulative_distance += distance
        return cumulative_distance
    
    def _setup_progress_tangents(self):
        """Calculate progress values and tangents for each segment."""
        point_progress = [0]
        segment_tangents = []
        
        for ix, point in enumerate(self._points):
            if ix > 0:
                segment = point - self._points[ix - 1]
                segment_length = np.linalg.norm(segment)
                segment_tangent = segment / segment_length
                point_progress.append(segment_length / self._length + point_progress[ix - 1])
                segment_tangents.append(segment_tangent)
        
        segment_tangents.append(segment_tangents[-1])
        return point_progress, segment_tangents
    
    def pos_at(self, progress: float):
        """Get position at given progress [0, 1]."""
        if progress <= 0:
            return self._points[0]
        elif progress >= 1.0:
            return self._points[-1]
        
        path_ix = 0
        for ix, prog in enumerate(self._point_progress):
            if prog > progress:
                path_ix = ix
                break
        
        segment_distance = self._length * (progress - self._point_progress[path_ix - 1])
        return self._points[path_ix - 1] + self._segment_tangents[path_ix - 1] * segment_distance
    
    def update_waypoint(self):
        """Update waypoint based on current position."""
        if self.progress < 1.0:
            wp_disp = self.waypoint - self._agent_state.position
            wp_dist = np.linalg.norm(wp_disp)
            
            while wp_dist < self._threshold:
                self.progress += self._step_size
                self.waypoint = self.pos_at(self.progress)
                if self.progress >= 1.0:
                    self.progress = 1.0
                    break
                wp_disp = self.waypoint - self._agent_state.position
                wp_dist = np.linalg.norm(wp_disp)
    
    def set_state(self, agent_state):
        """Update agent state."""
        self._agent_state = agent_state
    
    def get_target_state(self):
        """Get target position and rotation."""
        self.update_waypoint()
        
        previous_rigid_state = habitat_sim.RigidState(
            utils.quat_to_magnum(self._agent_state.rotation),
            self._agent_state.position
        )
        
        time_step = 1.0 / 30.0
        self._track_waypoint(self.waypoint, previous_rigid_state, self.vel_control, dt=time_step)
        
        target_rigid_state = self.vel_control.integrate_transform(time_step, previous_rigid_state)
        position = target_rigid_state.translation
        rotation = utils.quat_from_magnum(target_rigid_state.rotation)
        
        return position, rotation
    
    def _track_waypoint(self, waypoint, rs, vc, dt: float = 1.0 / 60.0):
        """Track waypoint with velocity control."""
        glob_forward = rs.rotation.transform_vector(mn.Vector3(0, 0, -1.0)).normalized()
        glob_right = rs.rotation.transform_vector(mn.Vector3(-1.0, 0, 0)).normalized()
        
        to_waypoint = mn.Vector3(waypoint) - rs.translation
        u_to_waypoint = to_waypoint.normalized()
        angle_error = float(mn.math.angle(glob_forward, u_to_waypoint))
        
        # Linear velocity
        if angle_error < ANGULAR_ERROR_THRESHOLD:
            new_velocity = (vc.linear_velocity[2] - MAX_LINEAR_SPEED) / 2.0
        else:
            new_velocity = (vc.linear_velocity[2]) / 2.0
        
        vc.linear_velocity = mn.Vector3(0, 0, new_velocity)
        
        # Angular velocity
        rot_dir = 1.0 if mn.math.dot(glob_right, u_to_waypoint) >= 0 else -1.0
        if angle_error > (MAX_TURN_SPEED * 10.0 * dt):
            angular_correction = MAX_TURN_SPEED
        else:
            angular_correction = angle_error / 2.0
        
        vc.angular_velocity = mn.Vector3(
            0, np.clip(rot_dir * angular_correction, -MAX_TURN_SPEED, MAX_TURN_SPEED), 0
        )


def filter_forward_path(position, rotation, path: List) -> List:
    """Filter out points behind the current position."""
    rotation_obj = R.from_quat([rotation.x, rotation.y, rotation.z, rotation.w])
    forward_vector_3d = rotation_obj.apply([0, 0, -1])
    forward_vector = np.array([forward_vector_3d[0], forward_vector_3d[2]])
    forward_vector = forward_vector / np.linalg.norm(forward_vector)
    
    current_2d_position = position[[0, 2]]
    
    for i, point in enumerate(path):
        point_2d = point[[0, 2]]
        
        if np.allclose(point_2d, current_2d_position, atol=PATH_FILTER_TOLERANCE):
            print("Current position close to path point, using current position as start")
            return [position] + path[i + 1:]
        
        direction_to_point = point_2d - current_2d_position
        direction_norm = np.linalg.norm(direction_to_point)
        
        if direction_norm == 0:
            continue
        
        direction_to_point = direction_to_point / direction_norm
        dot_product = np.dot(forward_vector, direction_to_point)
        
        if dot_product > 0:
            return path[i:]
    
    return []


class NavigationHandler(BaseHandler):
    """Handler for navigation operations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Subscribe to events
        self.events.subscribe(EventType.NAVIGATION_START, self.handle_start_navigation)
        self.events.subscribe(EventType.NAVIGATION_STOP, self.handle_stop_navigation)
    
    def handle_start_navigation(self, event: Event):
        """Handle navigation start."""
        self.state.app.is_navigating = True
        self._setup_navigation()
    
    def handle_stop_navigation(self, event: Event):
        """Handle navigation stop."""
        self.state.app.is_navigating = False
        self.state.navigation.continuous_path_follower = None
    
    def _setup_navigation(self):
        """Setup navigation path and follower."""
        current_state = self.sim.get_agent_state()
        current_position = current_state.position
        current_rotation = current_state.rotation
        
        # Check for global path from ROS
        if self.state.navigation.previous_global_path is not None:
            pose_in_habitat = [
                np.array([x, current_position[1], z])
                for x, _, z in self.state.navigation.previous_global_path
            ]
            
            print(f"Current rotation: {current_rotation}")
            print(f"Current position: {current_position}")
            print(f"Current path length: {len(pose_in_habitat)}")
            
            pose_in_habitat = filter_forward_path(current_position, current_rotation, pose_in_habitat)
            print(f"Filtered path length: {len(pose_in_habitat)}")
            
            nav_goal = pose_in_habitat[-1]
            nav_path = pose_in_habitat
        else:
            # Generate random path
            goal, path_points = self.sim.compute_random_navigation_path()
            if goal is None:
                self.state.app.is_navigating = False
                return
            
            nav_goal = goal
            nav_path = path_points
        
        self.state.navigation.nav_goal = nav_goal
        self.state.navigation.nav_path = nav_path
        
        # Initialize path follower
        self.state.navigation.continuous_path_follower = ContinuousPathFollower(
            self.sim.sim,
            nav_path,
            current_state,
            waypoint_threshold=WAYPOINT_THRESHOLD
        )
    
    def update(self):
        """Update navigation if active."""
        follower = self.state.navigation.continuous_path_follower
        if follower is not None and follower.progress < 1.0:
            agent_state = self.sim.get_agent_state()
            follower.set_state(agent_state)
            
            pos, rot = follower.get_target_state()
            agent_state.position = pos
            agent_state.rotation = rot
            
            self.sim.set_agent_state(agent_state)
        elif follower is not None and follower.progress >= 1.0:
            # Navigation complete
            print("Navigation complete")
            self.state.app.is_navigating = False
            self.state.navigation.continuous_path_follower = None

