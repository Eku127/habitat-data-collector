"""Factory for creating Habitat simulator configurations."""

import json
from pathlib import Path
from typing import Union, List, Optional
import numpy as np
import habitat_sim
from omegaconf import DictConfig


class ConfigFactory:
    """Factory for creating Habitat simulator configurations."""
    
    @staticmethod
    def create_sensor_spec(
        uuid: str,
        sensor_type: habitat_sim.SensorType,
        height: int,
        width: int,
        position: Union[List, np.ndarray],
        orientation: Optional[Union[List, np.ndarray]] = None,
    ) -> habitat_sim.CameraSensorSpec:
        """Create a sensor specification.
        
        Args:
            uuid: Unique identifier for the sensor
            sensor_type: Type of sensor (COLOR, DEPTH, SEMANTIC)
            height: Image height
            width: Image width
            position: Sensor position [x, y, z]
            orientation: Optional sensor orientation [roll, pitch, yaw]
            
        Returns:
            Camera sensor specification
        """
        sensor_spec = habitat_sim.CameraSensorSpec()
        sensor_spec.uuid = uuid
        sensor_spec.sensor_type = sensor_type
        sensor_spec.resolution = [height, width]
        sensor_spec.position = position
        if orientation is not None:
            sensor_spec.orientation = orientation
        sensor_spec.sensor_subtype = habitat_sim.SensorSubType.PINHOLE
        return sensor_spec
    
    @staticmethod
    def create_simulator_config(cfg: DictConfig) -> habitat_sim.Configuration:
        """Create a complete Habitat simulator configuration.
        
        Args:
            cfg: Hydra configuration
            
        Returns:
            Habitat simulator configuration
        """
        # Simulator configuration
        sim_cfg = habitat_sim.SimulatorConfiguration()
        sim_cfg.gpu_device_id = 0
        
        # Load scene paths
        if cfg.load_from_config:
            with open(cfg.scene_config, "r") as file:
                config_data = json.load(file)
                scene_path = config_data['scene']['scene_path']
                scene_dataset_config = config_data['scene']['scene_dataset_config']
        else:
            scene_path = cfg.scene_path
            scene_dataset_config = cfg.scene_dataset_config
        
        sim_cfg.scene_id = scene_path
        sim_cfg.scene_dataset_config_file = scene_dataset_config
        sim_cfg.enable_physics = cfg.physics_cfg.enable_physics
        
        # Create sensor specifications
        sensor_specs = []
        
        # Back RGB sensor
        back_rgb_spec = ConfigFactory.create_sensor_spec(
            "back_color_sensor",
            habitat_sim.SensorType.COLOR,
            cfg.data_cfg.resolution.h,
            cfg.data_cfg.resolution.w,
            [0.0, cfg.data_cfg.camera_height, 1.3],
            orientation=[-np.pi / 8, 0.0, 0.0],
        )
        sensor_specs.append(back_rgb_spec)
        
        # Front RGB sensor
        if cfg.data_cfg.rgb:
            rgb_spec = ConfigFactory.create_sensor_spec(
                "color_sensor",
                habitat_sim.SensorType.COLOR,
                cfg.data_cfg.resolution.h,
                cfg.data_cfg.resolution.w,
                [0.0, cfg.data_cfg.camera_height, 0.0],
            )
            sensor_specs.append(rgb_spec)
        
        # Depth sensor
        if cfg.data_cfg.depth:
            depth_spec = ConfigFactory.create_sensor_spec(
                "depth_sensor",
                habitat_sim.SensorType.DEPTH,
                cfg.data_cfg.resolution.h,
                cfg.data_cfg.resolution.w,
                [0.0, cfg.data_cfg.camera_height, 0.0],
            )
            sensor_specs.append(depth_spec)
        
        # Semantic sensor
        if cfg.data_cfg.semantic:
            semantic_spec = ConfigFactory.create_sensor_spec(
                "semantic_sensor",
                habitat_sim.SensorType.SEMANTIC,
                cfg.data_cfg.resolution.h,
                cfg.data_cfg.resolution.w,
                [0.0, cfg.data_cfg.camera_height, 0.0],
            )
            sensor_specs.append(semantic_spec)
        
        # Agent configuration
        agent_cfg = habitat_sim.agent.AgentConfiguration()
        agent_cfg.sensor_specifications = sensor_specs
        agent_cfg.action_space = {
            "move_forward": habitat_sim.agent.ActionSpec(
                "move_forward",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.move_forward),
            ),
            "turn_left": habitat_sim.agent.ActionSpec(
                "turn_left",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.turn_left),
            ),
            "turn_right": habitat_sim.agent.ActionSpec(
                "turn_right",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.turn_right),
            ),
            "move_backward": habitat_sim.agent.ActionSpec(
                "move_backward",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.move_backward),
            ),
            "look_up": habitat_sim.agent.ActionSpec(
                "look_up",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.look_up),
            ),
            "look_down": habitat_sim.agent.ActionSpec(
                "look_down",
                habitat_sim.agent.ActuationSpec(amount=cfg.movement_cfg.look_down),
            ),
        }
        
        return habitat_sim.Configuration(sim_cfg, [agent_cfg])

