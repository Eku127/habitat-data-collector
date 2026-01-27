"""Coordinate transformation utilities.

Handles transformations between:
- Habitat coordinate system (cam_habi, world_habi): Y-Up, -Z-Forward, X-Right
- Standard coordinate system (cam_sys, world_sys): 
    - cam_sys: Y-Down, Z-Forward, X-Right (typical camera)
    - world_sys: Z-Up, Y-Forward, X-Right
"""

import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import List, Tuple


class CoordinateTransform:
    """Coordinate transformation utilities."""
    
    # Transformation matrices (defined once, used everywhere)
    WORLD_HABI_TO_WORLD_SYS = np.array([
        [1,  0,  0, 0],
        [0,  0, -1, 0],
        [0,  1,  0, 0],
        [0,  0,  0, 1]
    ], dtype=np.float64)
    
    CAM_SYS_TO_CAM_HABI = np.array([
        [1,  0,  0, 0],
        [0, -1,  0, 0],
        [0,  0, -1, 0],
        [0,  0,  0, 1]
    ], dtype=np.float64)
    
    # Inverse matrices
    WORLD_SYS_TO_WORLD_HABI = np.linalg.inv(WORLD_HABI_TO_WORLD_SYS)
    CAM_HABI_TO_CAM_SYS = np.linalg.inv(CAM_SYS_TO_CAM_HABI)
    
    @classmethod
    def habitat_to_system_pose(cls, position: np.ndarray, rotation_quat: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert Habitat pose to system coordinate pose.
        
        Args:
            position: Position in Habitat coordinates [x, y, z]
            rotation_quat: Rotation quaternion [x, y, z, w] in Habitat coords
            
        Returns:
            Tuple of (position, rotation_quat) in system coordinates
        """
        # Convert quaternion to rotation matrix
        rotation_matrix = R.from_quat(rotation_quat).as_matrix()
        
        # Create 4x4 transformation matrix (cam_habi to world_habi)
        cam_habi_to_world_habi = np.eye(4)
        cam_habi_to_world_habi[:3, :3] = rotation_matrix
        cam_habi_to_world_habi[:3, 3] = position
        
        # Transform: world_habi -> world_sys -> cam_sys
        cam_sys_to_world_sys = (
            cls.WORLD_HABI_TO_WORLD_SYS @ 
            cam_habi_to_world_habi @ 
            cls.CAM_SYS_TO_CAM_HABI
        )
        
        # Extract position and rotation
        transformed_position = cam_sys_to_world_sys[:3, 3]
        transformed_rotation_matrix = cam_sys_to_world_sys[:3, :3]
        transformed_rotation = R.from_matrix(transformed_rotation_matrix).as_quat()
        
        return transformed_position, transformed_rotation
    
    @classmethod
    def system_to_habitat_pose(cls, pose_sys: np.ndarray) -> np.ndarray:
        """Convert system pose (4x4 matrix) to Habitat pose.
        
        Args:
            pose_sys: 4x4 transformation matrix in system coordinates
            
        Returns:
            4x4 transformation matrix in Habitat coordinates
        """
        # world_sys_to_world_habi @ cam_sys_to_world_sys @ cam_habi_to_cam_sys
        cam_habi_to_world_habi = (
            cls.WORLD_SYS_TO_WORLD_HABI @ 
            pose_sys @ 
            cls.CAM_HABI_TO_CAM_SYS
        )
        return cam_habi_to_world_habi
    
    @classmethod
    def get_agent_pose_in_system(cls, sensor_state) -> List[float]:
        """Get agent pose in system coordinates [x, y, z, qx, qy, qz, qw].
        
        Args:
            sensor_state: Habitat sensor state
            
        Returns:
            Pose as list [x, y, z, qx, qy, qz, qw] in system coordinates
        """
        position = np.array([
            sensor_state.position[0],
            sensor_state.position[1],
            sensor_state.position[2]
        ])
        
        rotation = sensor_state.rotation
        rotation_quat = np.array([rotation.x, rotation.y, rotation.z, rotation.w])
        
        transformed_position, transformed_rotation = cls.habitat_to_system_pose(
            position, rotation_quat
        )
        
        return list(transformed_position) + list(transformed_rotation)
    
    @classmethod
    def transform_path_to_habitat(cls, path_sys: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Transform a path from system coordinates to Habitat coordinates.
        
        Args:
            path_sys: List of (x, y, z) tuples in system coordinates
            
        Returns:
            List of (x, y, z) tuples in Habitat coordinates
        """
        path_habitat = []
        
        for point in path_sys:
            # Create 4x4 matrix with only translation
            pose_sys = np.eye(4)
            pose_sys[:3, 3] = np.array(point)
            
            # Transform to Habitat
            transformed_pose = cls.system_to_habitat_pose(pose_sys)
            
            # Extract position
            transformed_point = tuple(transformed_pose[:3, 3])
            path_habitat.append(transformed_point)
        
        return path_habitat
    
    @classmethod
    def convert_to_topdown(cls, pathfinder, point: np.ndarray, meters_per_pixel: float) -> np.ndarray:
        """Convert 3D point to topdown map coordinates.
        
        Args:
            pathfinder: Habitat pathfinder object
            point: 3D point [x, y, z]
            meters_per_pixel: Scale factor for topdown map
            
        Returns:
            2D point [px, py] in topdown map coordinates
        """
        bounds = pathfinder.get_bounds()
        
        # Convert 3D x,z to topdown x,y
        px = (point[0] - bounds[0][0]) / meters_per_pixel
        py = (point[2] - bounds[0][2]) / meters_per_pixel
        
        return np.array([px, py])

