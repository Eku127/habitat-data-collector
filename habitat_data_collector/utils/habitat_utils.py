# Standard library imports
import json
import math
import os
import random
import time
from collections import defaultdict
from pathlib import Path

# Third-party imports
import cv2
import magnum as mn
import numpy as np
import yaml
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf
from PIL import Image
from scipy.spatial.transform import Rotation as R
from tqdm import tqdm
from typing import Dict, List, Tuple, Union

# Habitat-sim and related utilities
import habitat_sim
from habitat_sim.utils.common import d3_40_colors_rgb
from habitat_sim.utils import common as utils
import habitat.sims.habitat_simulator.sim_utilities as sutils

def make_cfg(cfg: DictConfig) -> habitat_sim.Configuration:
    # Simulator configuration
    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.gpu_device_id = 0

    if cfg.load_from_config:
        # 从 JSON 配置文件加载场景路径和配置路径
        with open(cfg.scene_config, "r") as file:
            config_data = json.load(file)
            scene_path = config_data['scene']['scene_path']
            scene_dataset_config = config_data['scene']['scene_dataset_config']
    else:
        # 使用直接定义在 cfg 中的路径
        scene_path = cfg.scene_path
        scene_dataset_config = cfg.scene_dataset_config
    
    # define the scene
    sim_cfg.scene_id = scene_path
    # define the scene config for semantic
    sim_cfg.scene_dataset_config_file = scene_dataset_config

    # physics
    sim_cfg.enable_physics = cfg.physics_cfg.enable_physics

    # Sensor specifications
    sensor_spec = []

    # Back RGB sensor specification
    back_rgb_sensor_spec = make_sensor_spec(
        "back_color_sensor",
        habitat_sim.SensorType.COLOR,
        cfg.data_cfg.resolution.h,
        cfg.data_cfg.resolution.w,
        [0.0, cfg.data_cfg.camera_height, 1.3],
        orientation=[-np.pi / 8, 0.0, 0.0],
    )
    sensor_spec.append(back_rgb_sensor_spec)

    # Front RGB sensor specification
    if cfg.data_cfg.rgb:
        rgb_sensor_spec = make_sensor_spec(
            "color_sensor",
            habitat_sim.SensorType.COLOR,
            cfg.data_cfg.resolution.h,
            cfg.data_cfg.resolution.w,
            [0.0, cfg.data_cfg.camera_height, 0.0],
        )
        sensor_spec.append(rgb_sensor_spec)

    # Depth sensor specification
    if cfg.data_cfg.depth:
        depth_sensor_spec = make_sensor_spec(
            "depth_sensor",
            habitat_sim.SensorType.DEPTH,
            cfg.data_cfg.resolution.h,
            cfg.data_cfg.resolution.w,
            [0.0, cfg.data_cfg.camera_height, 0.0],
        )
        sensor_spec.append(depth_sensor_spec)

    # Semantic sensor specification
    if cfg.data_cfg.semantic:
        semantic_sensor_spec = make_sensor_spec(
            "semantic_sensor",
            habitat_sim.SensorType.SEMANTIC,
            cfg.data_cfg.resolution.h,
            cfg.data_cfg.resolution.w,
            [0.0, cfg.data_cfg.camera_height, 0.0],
        )
        sensor_spec.append(semantic_sensor_spec)

    # Agent configuration
    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = sensor_spec
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

    # Return the full configuration
    return habitat_sim.Configuration(sim_cfg, [agent_cfg])


def make_sensor_spec(
    uuid: str,
    sensor_type: str,
    h: int,
    w: int,
    position: Union[List, np.ndarray],
    orientation: Union[List, np.ndarray] = None,
) -> Dict:
    sensor_spec = habitat_sim.CameraSensorSpec()
    sensor_spec.uuid = uuid
    sensor_spec.sensor_type = sensor_type
    sensor_spec.resolution = [h, w]
    sensor_spec.position = position
    if orientation:
        sensor_spec.orientation = orientation

    sensor_spec.sensor_subtype = habitat_sim.SensorSubType.PINHOLE
    return sensor_spec


def keyboard_control_fast():
    k = cv2.waitKey(1)
    
    if k == ord("a"):
        action = "turn_left"
    elif k == ord("d"):
        action = "turn_right"
    elif k == ord("w"):
        action = "move_forward"
    elif k == ord("s"):
        action = "move_backward"
    elif k == ord("q"):
        action = "stop"
    elif k == ord("h"):
        action = "help"
    elif k == ord("m"):
        action = "map"
    elif k == ord("e"):
        action = "save_config"
    elif k == ord(" "):
        return k, "record"
    elif k == ord("="):
        return k, "add_object"
    elif k == ord("-"):
        return k, "remove_object"
    elif k == ord("p"):  # New key for placing objects in view
        return k, "place_in_view"
    elif k == ord("n"):  # New key for open naviagtion
        return k, "navigation"
    elif k == ord("g"):
        return k, "grab"
    elif k == ord("r"):
        return k, "release"

    # Arrow keys
    elif k == 81:  # Left arrow
        action = "turn_left"
    elif k == 83:  # Right arrow
        action = "turn_right"
    elif k == 82:  # Up arrow
        action = "look_up"
    elif k == 84:  # Down arrow
        action = "look_down"

    elif k == -1:
        return k, None
    else:
        return -1, None

    return k, action


def display_obs(obs, help_count, topdown_map = None, recording = False):
    # RGB obs
    rgb_obs = obs["color_sensor"]
    rgb_img_cv = cv2.cvtColor(np.array(rgb_obs), cv2.COLOR_RGB2BGR)


    # Border information for depth and semantic
    border_thickness = 5
    border_color = (128, 128, 128)  # Gray border color

    # Define positions to place the depth and semantic images on the RGB image
    start_x = 20  # X coordinate where the small images will be placed
    start_y = 20  # Y coordinate for the first image (depth)
    gap_size = 20  # Gap between depth and semantic images

    # Check if depth sensor data is available
    if "depth_sensor" in obs:
        # Depth obs
        depth_obs = obs["depth_sensor"]
        depth_normalized = cv2.normalize(depth_obs, None, 0, 255, cv2.NORM_MINMAX)
        depth_img_cv = depth_normalized.astype(np.uint8)
    else:
        # If no depth data is available, create a black image
        depth_img_cv = np.zeros((rgb_img_cv.shape[0], rgb_img_cv.shape[1]), dtype=np.uint8)

    # Resize depth image (whether real or black)
    depth_img_cv_resized = cv2.resize(depth_img_cv, (int(rgb_img_cv.shape[1] * 0.2), int(rgb_img_cv.shape[0] * 0.2)))

    # Add borders to the depth images
    depth_img_cv_bordered = cv2.copyMakeBorder(depth_img_cv_resized, border_thickness, border_thickness, border_thickness, border_thickness, cv2.BORDER_CONSTANT, value=border_color)

    # Place the depth image on the RGB image
    rgb_img_cv[start_y:start_y + depth_img_cv_bordered.shape[0], start_x:start_x + depth_img_cv_bordered.shape[1]] = cv2.cvtColor(depth_img_cv_bordered, cv2.COLOR_GRAY2BGR)
    
    # Check if semantic sensor data is available
    if "semantic_sensor" in obs:
        # Semantic obs
        semantic_obs = obs["semantic_sensor"]
        semantic_img = Image.new("P", (semantic_obs.shape[1], semantic_obs.shape[0]))
        semantic_img.putpalette(d3_40_colors_rgb.flatten())
        semantic_img.putdata((semantic_obs.flatten() % 40).astype(np.uint8))
        semantic_img = semantic_img.convert("RGB")
        semantic_img_cv = np.array(semantic_img)
        semantic_img_cv = cv2.cvtColor(semantic_img_cv, cv2.COLOR_RGB2BGR)
    else:
        # If no semantic data is available, create a black image
        semantic_img_cv = np.zeros((rgb_img_cv.shape[0], rgb_img_cv.shape[1], 3), dtype=np.uint8)

    # Resize the semantic images (whether real or black)
    semantic_img_cv_resized = cv2.resize(semantic_img_cv, (int(rgb_img_cv.shape[1] * 0.2), int(rgb_img_cv.shape[0] * 0.2)))

    # Add borders to the semantic images
    semantic_img_cv_bordered = cv2.copyMakeBorder(semantic_img_cv_resized, border_thickness, border_thickness, border_thickness, border_thickness, cv2.BORDER_CONSTANT, value=border_color)

    # Place the semantic image below the depth image
    rgb_img_cv[start_y + depth_img_cv_bordered.shape[0] + gap_size:start_y + depth_img_cv_bordered.shape[0] + gap_size + semantic_img_cv_bordered.shape[0],
            start_x:start_x + semantic_img_cv_bordered.shape[1]] = semantic_img_cv_bordered
        
    # Topdown map handling
    # Resize the topdown map to fit in the top right corner of the RGB image
    if topdown_map is not None:
        map_height, map_width = topdown_map.shape[:2]
        aspect_ratio = map_width / map_height
        new_height = int(rgb_img_cv.shape[0] * 0.25)
        new_width = int(aspect_ratio * new_height)

        # Resize keeping the aspect ratio
        topdown_map_resized = cv2.resize(topdown_map, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

        # Convert topdown_map to BGR if necessary
        if len(topdown_map_resized.shape) == 2 or topdown_map_resized.shape[2] == 1:
            topdown_map_resized_bgr = cv2.cvtColor(topdown_map_resized, cv2.COLOR_GRAY2BGR)
        else:
            topdown_map_resized_bgr = topdown_map_resized

        # Define position to place the topdown map (right corner)
        topdown_start_x = rgb_img_cv.shape[1] - topdown_map_resized_bgr.shape[1] - 20  # Leave some padding
        topdown_start_y = 20  # Start at the top, with padding

        # Place the topdown map in the top right corner of the RGB image
        rgb_img_cv[topdown_start_y:topdown_start_y + topdown_map_resized_bgr.shape[0],
                topdown_start_x:topdown_start_x + topdown_map_resized_bgr.shape[1]] = topdown_map_resized_bgr



    # Help messages
    # Add help text below the semantic image
    help_start_y = start_y + depth_img_cv_bordered.shape[0] + gap_size + semantic_img_cv_bordered.shape[0] + gap_size  # Y position for help text

    # Define help message to display
    help_message = """
    System Controls:
    space:           Start recording
    q:               Exit and save recording.
    h:               Display help message.
    m:              Display topdown map.

    Agent Controls:
    wasd:            Move forward/backward, turn left/right.
    Arrow keys:      Turn left/right, camera look up/down.
    """

    # Split the message into multiple lines
    help_lines = help_message.strip().split('\n')

    # Check if help_count is odd, if so, display "help"
    if help_count % 2 == 1:
        # Display each line of help message
        for i, line in enumerate(help_lines):
            line = line.strip()
            position = (start_x, help_start_y + i * 28)  # Left align by setting constant x position (start_x)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            color = (255, 255, 255)  # White text
            thickness = 1
            cv2.putText(rgb_img_cv, line, position, font, font_scale, color, thickness, cv2.LINE_AA)

    # REC indicator
    rec_color = (169, 169, 169)  # Gray when not recording
    rec_text = "REC"
    dot_color = (169, 169, 169)  # None means no dot when not recording

    # Flashing effect for "REC" text
    current_time = time.time()
    if recording:
        if int(current_time) % 2 == 0:  # Flash every second (appear/disappear)
            rec_color = (0, 0, 255)  # Red when recording
            dot_color = (0, 0, 255)  # Red dot when recording
        else:
            rec_text = ""  # Make the text disappear every other second
            dot_color = None

    # Add red dot and "REC" to the bottom-right corner
    rec_position = (rgb_img_cv.shape[1] - 80, rgb_img_cv.shape[0] - 30)
    dot_position = (rgb_img_cv.shape[1] - 93, rgb_img_cv.shape[0] - 40)  # Red dot before "REC"

    # Draw the red dot only if it should be visible
    if dot_color is not None:
        cv2.circle(rgb_img_cv, dot_position, 10, dot_color, -1)  # Solid circle

    # Draw the "REC" text
    cv2.putText(rgb_img_cv, rec_text, rec_position, cv2.FONT_HERSHEY_SIMPLEX, 1, rec_color, 2, cv2.LINE_AA)

    # Show the final image
    cv2.imshow("RGB with Depth and Semantic", rgb_img_cv)

def save_states(save_dir, agent_states):
    save_path = Path(save_dir) / "poses.txt"
    print(save_path)

    with open(save_path, "w") as f:
        sep = ""
        for agent_state in agent_states:
            sensor_state = agent_state.sensor_states["color_sensor"]
            pos = sensor_state.position
            quat = [
                sensor_state.rotation.x,
                sensor_state.rotation.y,
                sensor_state.rotation.z,
                sensor_state.rotation.w,
            ]
            f.write(f"{sep}{pos[0]}\t{pos[1]}\t{pos[2]}\t{quat[0]}\t{quat[1]}\t{quat[2]}\t{quat[3]}")
            sep = "\n"


def save_obs(
    root_save_dir: Union[str, Path], cfg: DictConfig, observations: Dict, action_timestamp: float
) -> None:
    """
    Save rgb, depth, or semantic images in the observation dictionary according to the sim_setting.
    obj2cls is a dictionary mapping from object id to semantic id in habitat_sim.
    rgb are saved as .png files of shape (width, height) in sim_setting.
    depth are saved as .npy files where each pixel stores depth in meters.
    semantic are saved as .npy files where each pixel stores semantic id.
    """
    root_save_dir = Path(root_save_dir)
    
    # Format the timestamp with fixed width, using 15 characters and 6 decimal places
    formatted_timestamp = f"{action_timestamp:015.7f}"
    
    if cfg.data_cfg.rgb:
        # Save rgb
        save_name = f"{formatted_timestamp}.png"
        save_dir = root_save_dir / "rgb"
        os.makedirs(save_dir, exist_ok=True)
        save_path = save_dir / save_name
        obs = observations["color_sensor"][:, :, [2, 1, 0]] / 255
        cv2.imwrite(str(save_path), observations["color_sensor"][:, :, [2, 1, 0]])

    if cfg.data_cfg.depth:
        save_name = f"{formatted_timestamp}.png"
        save_dir = root_save_dir / "depth"
        os.makedirs(save_dir, exist_ok=True)
        save_path = save_dir / save_name
        obs = observations["depth_sensor"]
        obs = (obs * 1000).astype(np.uint16)
        cv2.imwrite(save_path, obs)

    # if cfg.data_cfg.semantic:
    #     save_name = f"{save_id:06}.npy"
    #     save_dir = root_save_dir / "semantic"
    #     os.makedirs(save_dir, exist_ok=True)
    #     save_path = save_dir / save_name
    #     obs = observations["semantic_sensor"]
    #     obs = cvt_obj_id_2_cls_id(obs, obj2cls)
    #     with open(save_path, "wb") as f:
    #         np.save(f, obs)

def cvt_obj_id_2_cls_id(semantic: np.ndarray, obj2cls: Dict) -> np.ndarray:
    h, w = semantic.shape
    semantic = semantic.flatten()
    u, inv = np.unique(semantic, return_inverse=True)
    return np.array([obj2cls[x][0] for x in u])[inv].reshape((h, w))

def shrink_false_areas(topdown_map, iterations=1, kernel_size=3):
    """
    Shrinks the False areas in the topdown_map by expanding the True areas.

    Parameters:
        topdown_map (np.array): The input binary image containing True (representing obstacles) and False (representing free space).
        iterations (int): Number of dilation iterations; higher values lead to smaller False areas.
        kernel_size (int): Size of the kernel used to control the dilation intensity; larger values result in more shrinkage of the False areas.

    Returns:
        np.array: The topdown_map with shrunk False areas.
    """
    # Convert the boolean image to uint8 type, with True -> 255 and False -> 0
    map_uint8 = (topdown_map * 255).astype(np.uint8)
    
    # Define the kernel for the dilation operation
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

    # Dilate the True areas
    dilated_map = cv2.dilate(map_uint8, kernel, iterations=iterations)
    
    # Convert the dilated image back to boolean values
    shrunk_map = dilated_map > 127  # Values above 127 are considered True
    
    return shrunk_map

def check_vaild_in_topdown(key_point, topdown_map) -> bool:
    """
    检查给定的关键点是否落在原始 topdown_map 的白色区域(False)。

    参数:
        topdown_map (np.array): 输入的原始 topdown 地图,包含布尔值 True 表示障碍物,False 表示空地）。
        key_point (tuple): 要检查的点，格式为 (x, y)。
    
    返回:
        bool: 如果点落在白色区域(False)返回 True, 否则返回 False。
    """

    # 获取地图的尺寸
    height, width = topdown_map.shape

    # 检查 key_point 是否在地图范围内
    x, y = int(key_point[0]), int(key_point[1])
    if x < 0 or y < 0 or x >= width or y >= height:
        print("Warning: Key point is out of the map range.")
        return False  # 超出边界

    # 检查 key_point 是否落在白色区域（False）
    return not topdown_map[y, x]  # False 表示空地（白色区域）


def get_topdown_map_cv(
    topdown_map,
    agent_position=None,
    all_rigid_objects_positions=None,
    goal_position=None,
    nav_path=None,
):
    """
    Generates a topdown map with the agent position in red and rigid objects positions in green.
    
    Parameters:
        topdown_map (np.array): The original topdown map containing True and False values.
        agent_position (tuple): The (x, y) position of the agent on the map.
        all_rigid_objects_positions (list): List of (x, y) positions for all rigid objects on the map.
    
    Returns:
        np.array: An image with the topdown map and highlighted positions.
    """
    # Convert True to gray (128) and False to white (255)
    display_map = np.where(topdown_map, 128, 255).astype(np.uint8)

    # Use OpenCV's dilation operation to find edges
    kernel = np.ones((3, 3), np.uint8)
    dilated_map = cv2.dilate(topdown_map.astype(np.uint8), kernel, iterations=1)
    edges = dilated_map - topdown_map.astype(np.uint8)

    # Mark edges as black (0)
    display_map[edges == 1] = 0

    # Find the boundaries of the True region in topdown_map
    coords = np.argwhere(topdown_map)
    if coords.size > 0:
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        display_map_cropped = display_map[y_min:y_max + 1, x_min:x_max + 1]
    else:
        display_map_cropped = display_map

    # Add a border around the map
    border_size = 5
    display_map_cropped = cv2.copyMakeBorder(
        display_map_cropped, border_size, border_size, border_size, border_size, 
        cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )

    # Convert the cropped grayscale map to BGR format for color annotations
    if len(display_map_cropped.shape) == 2:
        display_map_cropped = cv2.cvtColor(display_map_cropped, cv2.COLOR_GRAY2BGR)

    # Plot agent position in red
    if agent_position is not None:
        agent_x = int(agent_position[0] - x_min + border_size)
        agent_y = int(agent_position[1] - y_min + border_size)
        cv2.circle(display_map_cropped, (agent_x, agent_y), 3, (0, 0, 255), -1)  # Red color for agent

    # Plot rigid objects positions in green
    if all_rigid_objects_positions is not None:
        for obj_position in all_rigid_objects_positions:
            obj_x = int(obj_position[0] - x_min + border_size)
            obj_y = int(obj_position[1] - y_min + border_size)
            cv2.circle(display_map_cropped, (obj_x, obj_y), 3, (0, 255, 0), -1)  # Green color for objects

    # Plot goal position in blue
    if goal_position is not None:
        goal_x = int(goal_position[0] - x_min + border_size)
        goal_y = int(goal_position[1] - y_min + border_size)
        cv2.circle(display_map_cropped, (goal_x, goal_y), 3, (255, 0, 0), -1)  # Blue color for goal

    # Plot navigation path in yellow
    if nav_path is not None:
        for i in range(1, len(nav_path)):
            start = nav_path[i - 1]
            end = nav_path[i]
            start_x = int(start[0] - x_min + border_size)
            start_y = int(start[1] - y_min + border_size)
            end_x = int(end[0] - x_min + border_size)
            end_y = int(end[1] - y_min + border_size)
            cv2.line(display_map_cropped, (start_x, start_y), (end_x, end_y), (0, 255, 255), 1)  # Yellow line for path

    return display_map_cropped

def convert_points_to_topdown(pathfinder, point, meters_per_pixel):
    bounds = pathfinder.get_bounds()
    
    # convert 3D x,z to topdown x,y
    px = (point[0] - bounds[0][0]) / meters_per_pixel
    py = (point[2] - bounds[0][2]) / meters_per_pixel

    return np.array([px, py])

def get_camera_intrinsics(sim, sensor_name):
    # Get render camera
    render_camera = sim._sensors[sensor_name]._sensor_object.render_camera

    # Get projection matrix
    projection_matrix = render_camera.projection_matrix

    # Get resolution (width and height)
    width, height = render_camera.viewport

    # Intrinsic calculation
    fx = projection_matrix[0, 0] * width / 2.0
    fy = projection_matrix[1, 1] * height / 2.0
    cx = (projection_matrix[2, 0] + 1.0) * width / 2.0
    cy = (projection_matrix[2, 1] + 1.0) * height / 2.0

    return fx, fy, cx, cy, width, height

def save_intrinsics(filepath, fx, fy, cx, cy, width, height):
    # 存储相机内参到字典
    intrinsics_data = {
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
        "width": width,
        "height": height
    }
    # 保存到 JSON 文件
    with open(filepath, "w") as f:
        json.dump(intrinsics_data, f, indent=4)


def print_scene_objects_info(scene, limit_output=500):
    """
    输出场景中每个区域的物体的类别、名称和AABB信息。
    """
    print(
        f"House has {len(scene.regions)} regions and {len(scene.objects)} objects."
    )
    
    count = 0  # 限制输出数量

    for region in scene.regions:
        print(
            f"Region ID: {region.id}, Category: {region.category.name() if region.category else 'Unknown'},"
            f" Center: x={region.aabb.center[0]:.2f}, y={region.aabb.center[1]:.2f}, z={region.aabb.center[2]:.2f},"
            f" Dimensions: x={region.aabb.sizes[0]:.2f}, y={region.aabb.sizes[1]:.2f}, z={region.aabb.sizes[2]:.2f}"
        )
        for obj in region.objects:
            category_name = obj.category.name() if obj.category else "Unknown"
            category_id = obj.category.index() if obj.category else -1
            print(f"    Object ID: {obj.id}")
            print(f"      Category: {category_name} (ID: {category_id})")
            print(f"      AABB Center: x={obj.aabb.center[0]:.2f}, y={obj.aabb.center[1]:.2f}, z={obj.aabb.center[2]:.2f}")
            print(f"      AABB Size: x={obj.aabb.sizes[0]:.2f}, y={obj.aabb.sizes[1]:.2f}, z={obj.aabb.sizes[2]:.2f}")
            print("-" * 50)
                
            count += 1
            if count >= limit_output:
                print("Reached output limit.")
                return


EXCLUDE_CATEGORIES = {"floor", "ceiling", "wall", "door", "void", "unknown"}

def save_scene_object_info(scene, scene_dir):
    """
    Save scene object information into two files:
    - class_bbox: Stores each category and its bounding boxes.
    - class_num: Stores each category and its count, sorted by count in descending order.
    
    Parameters:
        scene: The habitat scene containing objects and regions.
        scene_dir: Configuration object with the output path (cfg.output).
    """
    
    # Dictionaries to store data
    class_bbox = defaultdict(list)  # Maps category -> list of bounding boxes (AABB)
    class_count = defaultdict(int)  # Maps category -> count of objects
    
    # Traverse the scene's regions and objects
    for region in scene.regions:
        for obj in region.objects:
            category_name = obj.category.name() if obj.category else "unknown"
            
            # Get bounding box (AABB) details: center and size
            bbox = {
                'center': obj.aabb.center.tolist(),  # Convert ndarray to list
                'sizes': obj.aabb.sizes.tolist()     # Convert ndarray to list
            }
            
            # Add the bbox to the corresponding class
            class_bbox[category_name].append(bbox)
            
            # Increment the count for the category
            class_count[category_name] += 1
    
    # Sort class_count by count in descending order
    sorted_class_count = sorted(class_count.items(), key=lambda x: x[1], reverse=True)
    
    # Prepare file paths
    class_bbox_file = os.path.join(scene_dir, "class_bbox.json")
    class_num_file = os.path.join(scene_dir, "class_num.json")
    
    # Save class_bbox to JSON file
    with open(class_bbox_file, 'w') as f:
        json.dump(class_bbox, f, indent=4)
    
    # Save class_num to JSON file, sorted by count
    with open(class_num_file, 'w') as f:
        json.dump(sorted_class_count, f, indent=4)
    
    print(f"Saved class_bbox to {class_bbox_file}")
    print(f"Saved class_num to {class_num_file}")

def draw_bounding_boxes_for_category(sim, obj_attr_mgr, category_name):
    """
    为指定类别的物体添加红色粗线包围盒，并统计找到的物体数量。
    """
    scene = sim.semantic_scene
    found_count = 0  # 计数找到的物体数量

    # 遍历场景中的每个物体
    for obj in scene.objects:
        obj_category_name = obj.category.name() if obj.category else None
        if obj_category_name == category_name:
            found_count += 1
            # 获取对象的AABB信息
            aabb = obj.aabb
            center = aabb.center
            sizes = aabb.sizes * 0.5

            # 创建红色粗线包围盒
            cube_handle = obj_attr_mgr.get_template_handles("cubeWireframe")[0]
            cube_template_cpy = obj_attr_mgr.get_template_by_handle(cube_handle)
            cube_template_cpy.scale = sizes  # 设置包围盒尺寸
            cube_template_cpy.is_collidable = False

            bbox_handle = f"{category_name}_bbox_{found_count}"
            obj_attr_mgr.register_template(cube_template_cpy, bbox_handle)

            # 添加包围盒对象到场景并设置位置
            bbox_obj = sim.get_rigid_object_manager().add_object_by_template_handle(bbox_handle)
            bbox_obj.translation = center  # 设置包围盒中心位置
            bbox_obj.motion_type = habitat_sim.physics.MotionType.STATIC

            print(f"Added bounding box for {category_name} with Object ID: {obj.id}")

    print(f"Total {found_count} objects found for category '{category_name}'.")
    if found_count == 0:
        print(f"No objects found for category '{category_name}'.")

def draw_bounding_boxes_for_placable_categories(sim, obj_attr_mgr, placable_categories):
    """
    为指定类别的物体添加普通包围盒。
    """
    scene = sim.semantic_scene
    found_count = 0  # 计数找到的物体数量

    # 遍历场景中的每个物体
    for obj in scene.objects:
        obj_category_name = obj.category.name() if obj.category else None
        if obj_category_name in placable_categories:
            found_count += 1
            # 获取对象的AABB信息
            aabb = obj.aabb
            center = aabb.center
            sizes = aabb.sizes * 0.5

            # 创建包围盒
            cube_handle = obj_attr_mgr.get_template_handles("cubeWireframe")[0]
            cube_template_cpy = obj_attr_mgr.get_template_by_handle(cube_handle)
            cube_template_cpy.scale = sizes  # 设置包围盒尺寸
            cube_template_cpy.is_collidable = False

            bbox_handle = f"{obj_category_name}_bbox_{found_count}"
            obj_attr_mgr.register_template(cube_template_cpy, bbox_handle)

            # 添加包围盒对象到场景并设置位置
            bbox_obj = sim.get_rigid_object_manager().add_object_by_template_handle(bbox_handle)
            bbox_obj.translation = center  # 设置包围盒中心位置
            bbox_obj.motion_type = habitat_sim.physics.MotionType.STATIC

            print(f"Drawn bounding box for object {obj.id} with category '{obj_category_name}'")

    print(f"Total {found_count} objects found for specified categories.")

def get_bounding_boxes_for_category(sim, category_name):
    """
    获取指定类别的所有物体的包围盒信息（包括中心和大小），并输出信息。

    参数:
        sim (habitat_sim.Simulator): Habitat模拟器实例
        category_name (str): 需要获取包围盒信息的物体类别名称。
    
    返回:
        list: 包含指定类别物体的包围盒信息字典，每个字典包含 'Object ID', 'Category', 'center' 和 'size'。
    """

    scene = sim.semantic_scene
    bounding_boxes = []

    # 遍历场景中的每个物体
    for obj in scene.objects:
        if obj is None:  # 跳过 NoneType 对象
            continue
        
        obj_category_name = obj.category.name() if obj.category else None
        if obj_category_name == category_name:
            # 提取包围盒的中心和大小信息
            aabb_center = obj.aabb.center
            aabb_size = obj.aabb.sizes
            bounding_box_info = {
                "Object_ID": obj.id,
                "Category": category_name,
                "center": [aabb_center[0], aabb_center[1], aabb_center[2]],
                "size": [aabb_size[0], aabb_size[1], aabb_size[2]]
            }
            bounding_boxes.append(bounding_box_info)

    return bounding_boxes

def ensure_vector3(vec):
    """
    确保输入是magnum.Vector3类型。
    如果输入是列表或numpy数组,自动转换为Vector3。
    """
    if isinstance(vec, mn.Vector3):
        return vec
    return mn.Vector3(vec)

def draw_bounding_boxes(sim, obj_attr_mgr, bbox_list):
    """
    在场景中为给定的包围盒信息绘制边框。

    参数:
        sim (habitat_sim.Simulator): Habitat模拟器实例。
        obj_attr_mgr (habitat_sim.simulator.ObjectAttributesManager): 对象属性管理器。
        bbox_list (list): 包围盒信息列表，每个条目包含 'center' 和 'size'。
    """
    for i, bbox in enumerate(bbox_list):
        center = ensure_vector3(bbox["center"])  # 确保center为Vector3类型
        sizes = np.array(bbox["size"]) * 0.5  # 将包围盒缩放一半

        # 创建包围盒
        cube_handle = obj_attr_mgr.get_template_handles("cubeWireframe")[0]
        cube_template_cpy = obj_attr_mgr.get_template_by_handle(cube_handle)
        cube_template_cpy.scale = sizes  # 设置包围盒尺寸
        cube_template_cpy.is_collidable = False

        bbox_handle = f"bbox_{i}"
        obj_attr_mgr.register_template(cube_template_cpy, bbox_handle)

        # 添加包围盒对象到场景并设置位置
        bbox_obj = sim.get_rigid_object_manager().add_object_by_template_handle(bbox_handle)
        bbox_obj.translation = center  # 设置包围盒中心位置
        bbox_obj.motion_type = habitat_sim.physics.MotionType.STATIC

        print(f"Drawn bounding box with center {center} and size {sizes}")

def draw_bounding_box(sim, obj_attr_mgr, bbox):
    """
    在场景中为单个包围盒绘制边框。

    参数:
        sim (habitat_sim.Simulator): Habitat模拟器实例。
        obj_attr_mgr (habitat_sim.simulator.ObjectAttributesManager): 对象属性管理器。
        bbox (dict): 包围盒信息，包含 'center' 和 'size'。
    """
    center = ensure_vector3(bbox["center"])  # 确保center为Vector3类型
    sizes = np.array(bbox["size"]) * 0.5  # 将包围盒缩放一半

    # 创建包围盒
    cube_handle = obj_attr_mgr.get_template_handles("cubeWireframe")[0]
    cube_template_cpy = obj_attr_mgr.get_template_by_handle(cube_handle)
    cube_template_cpy.scale = sizes  # 设置包围盒尺寸
    cube_template_cpy.is_collidable = False

    bbox_handle = "single_bbox"
    obj_attr_mgr.register_template(cube_template_cpy, bbox_handle)

    # 添加包围盒对象到场景并设置位置
    bbox_obj = sim.get_rigid_object_manager().add_object_by_template_handle(bbox_handle)
    bbox_obj.translation = center  # 设置包围盒中心位置
    bbox_obj.motion_type = habitat_sim.physics.MotionType.STATIC

    print(f"Drawn single bounding box with center {center} and size {sizes}")

def is_on_ground(rigid_object, floor_height, tolerance=0.05):
    """
    Check if the object is on the ground by comparing its lowest point's y-coordinate with the floor height.

    Parameters:
        rigid_object: The object to check.
        floor_height (float): The height of the floor.
        tolerance (float): The tolerance range for considering the object to be on the ground.

    Returns:
        bool: True if the object is considered on the ground, False otherwise.
    """
    # Calculate the lowest point of the object based on its bounding box
    aabb = rigid_object.root_scene_node.compute_cumulative_bb()
    object_min_y = aabb.min[1] + rigid_object.translation[1]

    # Check if the lowest point is within tolerance range of the floor height
    return abs(object_min_y - floor_height) <= tolerance

def add_objects_to_bbox(sim, shrunk_map, given_bbox, object, sample_times=20):
    """
    尝试在给定的包围盒顶部随机放置对象，如果对象在有效的地图区域内，将其加入场景中。
    
    参数:
        sim (habitat_sim.Simulator): Habitat模拟器实例。
        shrunk_map (np.array): 收缩后的topdown_map, 用于判断对象是否放置在有效区域。
        given_bbox (dict): 包围盒信息，包含'center'和'size'。
        object (habitat_sim.RigidObject): 要放置的对象实例。
        sample_times (int): 尝试放置对象的次数。
    
    返回:
        bool: 如果成功放置对象返回True, 否则返回False。
    """

    # Get the floor height
    height = sim.pathfinder.get_bounds()[0][1]
    
    # Rotate the object to align it with the scene
    # object.rotation = mn.Quaternion.rotation(
    #     mn.Rad(-mn.math.pi_half), mn.Vector3(1.0, 0, 0)
    # )

    is_find = False

    # debugging
    sample_times = 1

    for _ in range(sample_times):
        # Generate a random position on top of the bounding box
        x = np.random.uniform(given_bbox['center'][0] - given_bbox['size'][0] / 2,
                              given_bbox['center'][0] + given_bbox['size'][0] / 2)
        y = given_bbox['center'][1] + given_bbox['size'][1] / 2 + 0.2  # Position on top of the bbox + 0.2 to avoid collision
        z = np.random.uniform(given_bbox['center'][2] - given_bbox['size'][2] / 2,
                              given_bbox['center'][2] + given_bbox['size'][2] / 2)
        object.translation = mn.Vector3(x, y, z)

        # Convert 3D position to top-down 2D point
        xy_point = convert_points_to_topdown(sim.pathfinder, object.translation, 0.05)

        # Check if the point is within a valid area in the top-down map
        if check_vaild_in_topdown(xy_point, shrunk_map):
            # If object placement is valid, snap it to the scene
            snap_success = sutils.snap_down(sim, object, [habitat_sim.stage_id])
            if snap_success:
                
                # Check if the object is on the ground
                if not is_on_ground(object, height, 0.3):
                    is_find = True
                    break
                else:
                    print("Warning: Object is on the ground.")
                    continue
            else:
                print("Warning: Failed to snap object to the scene.")

    if not is_find:
        print("Warning: Failed to find a suitable place for the object.")
        return False

    return True

def sample_and_place(sim, obj_handle_list, bbox_list, topdown_map, sample_times=100):

    # debugging
    sample_times = 1

    for _ in range(sample_times):
        # get a random object handle
        obj_handle = random.choice(obj_handle_list)

        rigid_object = sim.get_rigid_object_manager().add_object_by_template_handle(obj_handle)


        # get a random bounding box
        bbox = random.choice(bbox_list)

        # add the object to the bounding box
        if add_objects_to_bbox(sim, topdown_map, bbox, rigid_object):

            print(f"Object placed successfully. ID: {rigid_object.object_id}, Semantic ID: {rigid_object.semantic_id}")
            
            # 成功放置后，从对象句柄列表中移除
            obj_handle_list.remove(obj_handle)

            return rigid_object
        
    return None

def filter_bboxes_in_view(sim, bbox_list):
    """
    Filters bounding boxes that are within the view of the sensor and in front of the camera.

    Args:
        sim (habitat_sim.Simulator): The simulator instance.
        bbox_list (list): List of bounding boxes to filter, where each bbox is represented 
                          as a dictionary with "center" and "size".

    Returns:
        list: Filtered list of bounding boxes that are within the view of the sensor and 
              in front of the camera.
    """
    in_view_bboxes = []

    # Access the agent's render camera
    default_agent = sim.get_agent(0)

    render_camera = default_agent.scene_node.node_sensor_suite.get("color_sensor")
    render_cam = render_camera.render_camera

    # Get viewport dimensions
    viewport_width, viewport_height = render_cam.viewport

    for bbox in bbox_list:
        
        # 缩小 bbox 的 size（减少 15%）
        reduced_size = [dim * 0.80 for dim in bbox["size"]]

        # 创建一个新的 bbox，包含原始 center 和缩小后的 size
        reduced_bbox = {
            "center": bbox["center"],
            "size": reduced_size
        }

        # Convert bbox center to a magnum Vector3
        center_mn_vector = mn.Vector3(reduced_bbox["center"])

        # Project the 3D bbox center to 2D
        projected_point_3d = render_cam.projection_matrix.transform_point(
            render_cam.camera_matrix.transform_point(center_mn_vector)
        )

        # Convert to 2D pixel coordinates
        point_2d = mn.Vector2(projected_point_3d[0], -projected_point_3d[1])
        point_2d = point_2d / render_cam.projection_size()[0]
        point_2d += mn.Vector2(0.5)
        point_2d *= render_cam.viewport
        point_2d_int = mn.Vector2i(point_2d)

        # Check if the point is within the viewport bounds
        if 0 <= point_2d_int.x < viewport_width and 0 <= point_2d_int.y < viewport_height:
            in_view_bboxes.append(reduced_bbox)  # Add bbox to the list if in view

    return in_view_bboxes

def filter_rigid_objects(rigid_objects, floor_height, tolerance=0.05):
    objects_to_remove = []

    for rigid_object in rigid_objects:
        if is_on_ground(rigid_object, floor_height, tolerance):
            objects_to_remove.append(rigid_object)
            print(f"Object ID {rigid_object.object_id} is on the ground and marked for removal.")

    return objects_to_remove

def find_nearest_obj(sim, rigid_objects):
    # 获取智能体当前位置
    current_state = sim.get_agent(0).get_state()
    current_position = current_state.position

    # 初始化最近物体的距离和ID
    nearest_dist = float('inf')
    nearest_obj = None

    # 遍历所有物体，找到最近的物体
    for rigid_object in rigid_objects:
        # 获取物体的位置
        obj_pos = rigid_object.translation

        # 计算智能体与物体之间的欧氏距离
        dist = np.linalg.norm(np.array(current_position) - np.array(obj_pos))

        # 如果距离更近，则更新最近的物体和距离
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_obj = rigid_object
    
    return nearest_obj

def find_nearest_bbox(sim, bbox_list):
    """
    Finds the bounding box in the list that is closest to the agent's current position.

    Args:
        sim (habitat_sim.Simulator): The simulator instance.
        bbox_list (list): List of bounding boxes, where each bbox is represented 
                          as a dictionary with "center" and "size".

    Returns:
        dict: The bounding box that is closest to the agent's current position.
    """
    # 获取智能体的当前位置
    default_agent = sim.get_agent(0)
    current_position = default_agent.get_state().position

    nearest_bbox = None
    nearest_distance = float('inf')

    for bbox in bbox_list:
        # 获取 bbox 的中心位置
        bbox_center = np.array(bbox["center"])

        # 计算智能体当前位置和 bbox 中心的欧氏距离
        distance = np.linalg.norm(np.array(current_position) - bbox_center)

        # 如果找到更近的 bbox，更新最近的 bbox 和最小距离
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_bbox = bbox
    
    if nearest_bbox is not None:
        # 确保 size 是 numpy 数组以避免类型错误
        reduced_size = np.array(nearest_bbox["size"]) * 0.7

        reduced_bbox = {
            "center": nearest_bbox["center"],
            "size": reduced_size.tolist()  # 转回 list，保持与原数据一致
        }

        return reduced_bbox

    return None  # 如果 bbox_list 为空或找不到最近的 bbox

def place_object_to_bbox(sim, obj_handle, bbox, topdown_map, sample_times=100):

    sample_times = 1

    for _ in range(sample_times):

        rigid_object = sim.get_rigid_object_manager().add_object_by_template_handle(obj_handle)

        # add the object to the bounding box
        if add_objects_to_bbox(sim, topdown_map, bbox, rigid_object):

            print(f"Object placed successfully. ID: {rigid_object.object_id}, Semantic ID: {rigid_object.semantic_id}")

            return rigid_object
    
    return None

def register_templates_from_handles(obj_attr_mgr, cfg=None):
    """
    Registers templates from object attribute manager handles, using either predefined semantic IDs from a config file
    or assigning random IDs if no config is provided.

    Args:
        obj_attr_mgr: The object attribute manager to get and register templates.
        cfg: Configuration object with possible config file to load id-to-handle mapping.

    Returns:
        dict: A dictionary mapping each semantic ID to its handle.
    """
    # Get all handles from the file
    file_obj_handles = obj_attr_mgr.get_file_template_handles()
    
    # Dictionary to store semantic IDs and their handles
    id_handle_dict = {}

    # Load id-to-handle mappings from config if available
    config_data = {}
    if cfg and cfg.load_from_config:
        with open(cfg.scene_config, "r") as file:
            config_data = json.load(file).get("id_handle_mapping", {})

    # Traverse through each handle
    for handle in file_obj_handles:
        # Get a copy of this object's attributes template
        obj_template = obj_attr_mgr.get_template_by_handle(handle)
        
        # Extract key element from the file name
        filename = os.path.basename(handle)
        key_element = filename.split(".")[0]

        # Determine semantic ID: check if key_element is in config values, else assign random ID
        semantic_id = next((int(k) for k, v in config_data.items() if key_element in v), random.randint(0, 100))

        obj_template.semantic_id = semantic_id
        
        # Register the template with the new handle
        obj_attr_mgr.register_template(obj_template, key_element)
        
        # Store semantic ID and handle in the dictionary
        id_handle_dict[semantic_id] = key_element
        
        print(f"Registered {key_element} with semantic ID: {semantic_id}")

    return id_handle_dict

def save_config(cfg, all_rigid_objects, filepath):
    """
    保存场景配置和物体信息到 JSON 文件中。

    参数:
        cfg: 配置对象，包含场景的路径信息。
        id_handle_dict (dict): Handle 和 semantic ID 的映射关系。
        all_rigid_objects (list): 所有刚体物体的列表。
        filepath (str): 保存的 JSON 文件路径。
    """

    # 转换 DictConfig 到标准的 dict
    id_handle_dict = OmegaConf.to_container(cfg.id_handle_dict, resolve=True)

    # 提取并组织需要保存的信息，按顺序排列
    config_data = {
        'scene': {
            'scene_path': cfg.scene_path,
            'scene_dataset_config': cfg.scene_dataset_config
        },
        'id_handle_mapping': id_handle_dict,
        'objects': []
    }

    # 遍历所有刚体对象并提取其信息
    for obj in all_rigid_objects:
        # 获取并转换 translation 和 rotation 为列表格式
        translation_list = [obj.translation.x, obj.translation.y, obj.translation.z]
        rotation_list = [obj.rotation.vector.x, obj.rotation.vector.y, obj.rotation.vector.z, obj.rotation.scalar]
        
        # 将物体信息添加到配置数据，按顺序排列
        config_data['objects'].append({
            'object_id': obj.object_id,
            'translation': translation_list,
            'rotation': rotation_list,
            'semantic_id': obj.semantic_id
        })

    # 保存为 JSON 文件
    with open(filepath, "w") as file:
        json.dump(config_data, file, indent=4)
    
    print(f"Configuration saved to {filepath}")

def load_objects_from_config(sim, cfg):
    """
    Load objects from configuration file and place them in the simulation.

    Args:
        sim: The Habitat simulator instance.
        cfg: Configuration object that contains scene configuration paths and settings.
        id_handle_dict: Dictionary mapping semantic IDs to object handles.
    """
    # Load object configurations from the JSON file
    with open(cfg.scene_config, "r") as file:
        config_data = json.load(file)
    
    # Get the list of objects to add from the loaded configuration
    objects_info = config_data.get("objects", [])
    
    # Initialize the rigid object manager
    rigid_obj_mgr = sim.get_rigid_object_manager()

    # Added object list
    added_objects = []
    
    # Iterate over each object in the config
    for obj_data in objects_info:
        semantic_id = obj_data["semantic_id"]
        
        # Directly get the handle using semantic_id
        handle = cfg.id_handle_dict.get(semantic_id)
        
        if handle:
            # Add the object to the simulation using the handle
            rigid_object = rigid_obj_mgr.add_object_by_template_handle(handle)
            
            # Set object ID, translation, and rotation based on JSON data
            rigid_object.translation = mn.Vector3(*obj_data["translation"])

            # Convert rotation from list of 4 floats to Quaternion format
            rotation_vector = mn.Vector3(obj_data["rotation"][:3])  # First 3 components as Vector3
            rotation_scalar = obj_data["rotation"][3]  # Last component as scalar
            rigid_object.rotation = mn.Quaternion(rotation_vector, rotation_scalar)

            # Add the object to the list of added objects
            added_objects.append(rigid_object)
            
            print(f"Added object with ID {rigid_object.object_id}, Semantic ID {semantic_id}, "
                  f"at position {rigid_object.translation} with rotation {rigid_object.rotation}.")
        else:
            print(f"Warning: Semantic ID {semantic_id} does not have a matching handle.")

    return added_objects

def save_agent_states(save_dir, agent_states):
    """
    Save the agent states to a text file.

    Args:
        save_dir (str or Path): Directory where the states will be saved.
        agent_states (list): List of strings representing agent states with timestamp and pose.
    """
    save_path = Path(save_dir) / "pose.txt"
    with open(save_path, "w") as f:
        f.write("\n".join(agent_states))


def add_object_with_handle_and_pose(sim, object_handle, translation, rotation):
    rigid_obj_mgr = sim.get_rigid_object_manager()
    
    # Add the object to the simulation using the handle
    rigid_object = rigid_obj_mgr.add_object_by_template_handle(object_handle)

    # Set object translation (position)
    rigid_object.translation = mn.Vector3(*translation)

    # Convert rotation from list of 4 floats to Quaternion format
    rotation_vector = mn.Vector3(rotation[0], rotation[1], rotation[2])  # First 3 components as Vector3
    rotation_scalar = rotation[3]  # Last component as scalar
    rigid_object.rotation = mn.Quaternion(rotation_vector, rotation_scalar)

    return rigid_object  # Return the object if needed

def get_agent_pose(agent) -> List[float]:
    """
    Get the agent's pose (position and quaternion) from the simulator.
    Returns a pose is a list [x, y, z, qx, qy, qz, qw].
    """
    # Record agent state
    sensor_state = agent.get_state().sensor_states["color_sensor"]
    position = sensor_state.position  # [x, y, z]
    rotation = sensor_state.rotation  # quaternion (qx, qy, qz, qw)

    # Convert quaternion to rotation matrix
    rotation_matrix = R.from_quat([rotation.x, rotation.y, rotation.z, rotation.w]).as_matrix()

    # Create the 4x4 transformation matrix for cam_habi to world_habi
    transform_matrix = np.eye(4)
    transform_matrix[:3, :3] = rotation_matrix
    transform_matrix[:3, 3] = [position[0], position[1], position[2]]

    # Transformation matrices
    # world_habi to world_sys (from Habitat to World system)
    world_habi_to_world_sys = np.array([
        [1,  0,  0, 0],
        [0,  0,  -1, 0],
        [0,  1,  0, 0],
        [0,  0,  0, 1]
    ])

    # cam_sys to cam_habi (from Camera system to Habitat camera system)
    cam_sys_to_cam_habi = np.array([
        [1,  0,  0, 0],
        [0,  -1,  0, 0],
        [0,  0,  -1, 0],
        [0,  0,  0, 1]
    ])

    # Apply the transformations: world_habi -> world_sys -> cam_sys
    transform_matrix = world_habi_to_world_sys @ transform_matrix @ cam_sys_to_cam_habi

    # Pose in world_sys (x, y, z, qx, qy, qz, qw)
    transformed_position = transform_matrix[:3, 3]  # Extract position from the transformation matrix
    transformed_rotation_matrix = transform_matrix[:3, :3]  # Extract rotation matrix
    transformed_rotation = R.from_matrix(transformed_rotation_matrix).as_quat()  # Convert matrix to quaternion

    # Construct the pose in the format [x, y, z, qx, qy, qz, qw]
    pose = list(transformed_position) + list(transformed_rotation)

    return pose

def replay_and_save(sim, cfg, scene_dir, actions_list, init_record_state, init_record_time):
    print("Replay the recording and saving to disk...")

    # Output information storage
    agent_states = []

    # Initialize the state and the scene
    # Initialize the scene
    # if the scene is initialized from the scene config,
    # we also need loading all the objects from the config
    # clean all the rigid objects in the existing scene
    rigid_obj_mgr = sim.get_rigid_object_manager()
    rigid_obj_mgr.remove_all_objects()

    if cfg.load_from_config:
        print("Replay Initializaton: Loading objects from configuration...")
        load_objects_from_config(sim, cfg)

    # Initialize the state
    # set the agent to the init record state
    # TODO: Ask Alex Clegg about camera go up and down setting how to set state [FIXED]
    agent = sim.get_agent(cfg.default_agent)
    agent.set_state(init_record_state)
    agent_state = agent.get_state()
    agent_state.sensor_states["color_sensor"].position = init_record_state.sensor_states["color_sensor"].position
    agent_state.sensor_states["color_sensor"].rotation = init_record_state.sensor_states["color_sensor"].rotation
    agent_state.sensor_states["depth_sensor"].position = init_record_state.sensor_states["depth_sensor"].position
    agent_state.sensor_states["depth_sensor"].rotation = init_record_state.sensor_states["depth_sensor"].rotation
    agent_state.sensor_states["semantic_sensor"].position = init_record_state.sensor_states["semantic_sensor"].position
    agent_state.sensor_states["semantic_sensor"].rotation = init_record_state.sensor_states["semantic_sensor"].rotation

    agent.set_state(agent_state, reset_sensors=True, infer_sensor_states=False)

    # Initialize the replay_start_time
    # the init_record_time is an anchor
    replay_start_time = time.time()

    # traverse all the actions records with tqdm progress bar
    for idx, action_entry in enumerate(tqdm(actions_list, desc="Replaying and saving")):
        action = action_entry["action"]
        action_timestamp = action_entry["timestamp"]

        # sim physic steps first
        target_fps = cfg.frame_rate
        frame_interval = 1 / target_fps
        sim.step_physics(frame_interval)

        # make sure the time is okay
        if idx > 0:
            prev_timestamp = actions_list[idx - 1]["timestamp"]
            elapsed_time = action_timestamp - prev_timestamp
            current_time = time.time()
            sleep_time = elapsed_time - (current_time - replay_start_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

        obs = None

        if action is not None:
            if action == "add_object" or action == "place_in_view":
                # get other information from action entry
                semantic_id = action_entry["semantic_id"]
                object_handle = cfg.id_handle_dict.get(semantic_id)
                translation = action_entry["translation"]
                rotation = action_entry["rotation"]

                add_object_with_handle_and_pose(sim, object_handle, translation, rotation)

            elif action == "remove_object":
                # get the object id for removement
                object_id = action_entry["object_id"]
                rigid_obj_mgr.remove_object_by_id(object_id)
            else:
                # Simulate the action
                sim.step(action)

        obs = sim.get_sensor_observations()

        # here we save the obs
        save_obs(scene_dir, cfg, obs, action_timestamp)

        # Record agent state
        sensor_state = agent.get_state().sensor_states["color_sensor"]
        position = sensor_state.position
        rotation = sensor_state.rotation

        # Convert rotation (quaternion) to 3x3 rotation matrix
        rotation_matrix = R.from_quat([rotation.x, rotation.y, rotation.z, rotation.w]).as_matrix()

        # Create 4x4 transformation matrix
        # Pose collected is cam_habi to world_habi
        # cam_habi and world_habi coordinates are Y-Up, -Z-forward, X-Right
        # What we need is the pose in our system coordinate system
        # cam_sys is Y-Down, Z-forward, X-Right (Typical camera coordinate system)
        # world_sys is Z-Up, Y-forward, X-right, so we need transformation
        cam_habi_to_world_habi = np.eye(4)
        cam_habi_to_world_habi[:3, :3] = rotation_matrix
        cam_habi_to_world_habi[:3, 3] = [position[0], position[1], position[2]]

        world_habi_to_world_sys = np.array(
            [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]
        )

        cam_sys_to_cam_habi = np.array(
            [[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
        )
        cam_sys_to_world_sys = world_habi_to_world_sys @ cam_habi_to_world_habi @ cam_sys_to_cam_habi

        # Store state information as a 4x4 transformation matrix (flattened)
        transform_matrix_flat = cam_sys_to_world_sys.flatten()
        agent_states.append(f"{action_timestamp:015.7f}\t" + "\t".join(map(str, transform_matrix_flat)))

        # # IF Store state information with pos and quaternion
        # agent_states.append(f"{action_timestamp:015.7f} {position[0]} {position[1]} {position[2]} {rotation.x} {rotation.y} {rotation.z} {rotation.w}")

        # refresh the replay start time
        replay_start_time = time.time()

    save_agent_states(scene_dir, agent_states)
    print(f"Replay and saving obs and pose completed in {scene_dir}")

def get_habitat_pose(pose_sys):
    world_habi_to_world_sys = np.array(
        [[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]]
    )
    cam_sys_to_cam_habi = np.array(
        [[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
    )

    world_sys_to_world_habi = np.linalg.inv(world_habi_to_world_sys)
    cam_habi_to_cam_sys = np.linalg.inv(cam_sys_to_cam_habi)

    # world_sys_to_world_habi @ cam_sys_to_world_sys @ cam_habi_to_cam_sys
    cam_habi_to_world_habi = world_sys_to_world_habi @ pose_sys @ cam_habi_to_cam_sys

    return cam_habi_to_world_habi

def get_object_action_info(obj, timestamp, action):
    """
    Get action information for a manipulated object.

    Args:
        obj: The manipulated object.
        timestamp (float): The timestamp of the action.
        action (str): The action performed.

    Returns:
        dict: A dictionary containing action information.
    """
    if obj is not None:
        # Extract and convert translation and rotation to list format
        translation_list = [obj.translation.x, obj.translation.y, obj.translation.z]
        rotation_list = [obj.rotation.vector.x, obj.rotation.vector.y, obj.rotation.vector.z, obj.rotation.scalar]
        
        # Create the action info dictionary
        action_info = {
            "action": action,
            "timestamp": timestamp,
            "object_id": obj.object_id,
            "semantic_id": obj.semantic_id,
            "translation": translation_list,
            "rotation": rotation_list
        }
    else:
        # Handle case where obj is None (e.g., failed placement)
        action_info = {
            "action": action,
            "timestamp": timestamp,
            "object_id": None,
            "semantic_id": None,
            "translation": None,
            "rotation": None
        }

    return action_info

def compute_random_nav_path(sim):
    if not sim.pathfinder.is_loaded:
        print("Pathfinder not initialized, aborting.")
        return None, None
    # Get random navigable goal point
    goal = sim.pathfinder.get_random_navigable_point()
    current_state = sim.get_agent(0).get_state()

    path = habitat_sim.ShortestPath()

    path.requested_start = current_state.position
    path.requested_end = goal

    found_path = sim.pathfinder.find_path(path)

    path_points = path.points

    if len(path_points) == 0:
        print("No valid path found.")
        return None, None
    
    return goal, path_points

def filter_forward_path(position, rotation, path):
    """
    Filter out points in the path that are behind the current position based on the current direction.
    If a path point coincides with the current position, consider it as a forward point.

    Parameters:
    - position: numpy array, the current position in Habitat coordinates, shape (3,).
    - rotation: numpy array, the current rotation in Habitat coordinates as a quaternion (wxyz).
    - path: List of numpy arrays, each representing a 3D point in the path [(x1, y1, z1), ...].

    Returns:
    - filtered_path: List of numpy arrays, starting from the first point in front of the current position.
    """
    # Convert rotation quaternion (wxyz) to 2D forward vector (x, z only)
    rotation_obj = R.from_quat([rotation.x, rotation.y, rotation.z, rotation.w])
    forward_vector_3d = rotation_obj.apply([0, 0, -1])  # Forward vector in Habitat Y-Up, -Z-Forward system
    forward_vector = np.array([forward_vector_3d[0], forward_vector_3d[2]])  # Extract (x, z) components
    forward_vector = forward_vector / np.linalg.norm(forward_vector)  # Normalize

    # Current position in 2D (x, z)
    current_2d_position = position[[0, 2]]


    # Traverse the path
    for i, point in enumerate(path):
        # Convert path point to 2D (x, z)
        point_2d = point[[0, 2]]

        # If the current position is very close to the current position
        # Then we delete this point and add current position as the first point in the returning path
        if np.allclose(point_2d, current_2d_position, atol=0.03):
            print("Current position is close to the path point, Set the current position as the first point in the returning path")
            return [position] + path[i + 1:]

        # Compute direction vector from current position to path point
        direction_to_point = point_2d - current_2d_position
        direction_norm = np.linalg.norm(direction_to_point)

        # Skip if the norm is zero (this should be handled by the equality check above)
        if direction_norm == 0:
            continue

        direction_to_point = direction_to_point / direction_norm  # Normalize

        # Compute dot product
        dot_product = np.dot(forward_vector, direction_to_point)

        # If the point is in front, return this point and all subsequent points
        if dot_product > 0:
            return path[i:]

    # If no points are in front, return an empty list
    return []

# Here we add the important modules for navigation
class ContinuousPathFollower:
    def __init__(self, sim, path_points, agent_state, waypoint_threshold):
        self._sim = sim
        self._points = path_points
        assert len(self._points) > 0
        
        # 计算并缓存累计距离
        self._length = self.calculate_cumulative_distance()
        self._agent_state = agent_state
        self._threshold = waypoint_threshold
        self._step_size = 0.01
        self.progress = 0.0  # geodesic distance -> [0,1]
        self.waypoint = path_points[0]

        self.vel_control = habitat_sim.physics.VelocityControl()

        # 计算并缓存 progress 和 tangent 信息
        self._point_progress, self._segment_tangents = self._setup_progress_tangents()

        self.vel_control.controlling_lin_vel = True
        self.vel_control.lin_vel_is_local = True
        self.vel_control.controlling_ang_vel = True
        self.vel_control.ang_vel_is_local = True
        
        # Print for debug
        print("self._length = " + str(self._length))
        print("num points = " + str(len(self._points)))

    def _setup_progress_tangents(self):
        point_progress = [0]
        segment_tangents = []
        _length = self._length

        # 计算路径进度和切线
        for ix, point in enumerate(self._points):
            if ix > 0:
                segment = point - self._points[ix - 1]
                segment_length = np.linalg.norm(segment)
                segment_tangent = segment / segment_length
                point_progress.append(segment_length / _length + point_progress[ix - 1])
                segment_tangents.append(segment_tangent)

        segment_tangents.append(segment_tangents[-1])  # final tangent is duplicated
        return point_progress, segment_tangents

    def calculate_cumulative_distance(self):
        cumulative_distance = 0.0
        # 遍历相邻路径点，计算距离
        for i in range(1, len(self._points)):
            point_a = self._points[i-1]
            point_b = self._points[i]
            distance = np.linalg.norm(np.array(point_b) - np.array(point_a))
            cumulative_distance += distance
        return cumulative_distance

    def pos_at(self, progress):
        if progress <= 0:
            return self._points[0]
        elif progress >= 1.0:
            return self._points[-1]

        # 找到对应进度的路径点
        path_ix = 0
        for ix, prog in enumerate(self._point_progress):
            if prog > progress:
                path_ix = ix
                break

        # 计算目标点位置
        segment_distance = self._length * (progress - self._point_progress[path_ix - 1])
        return self._points[path_ix - 1] + self._segment_tangents[path_ix - 1] * segment_distance

    def update_waypoint(self):
        if self.progress < 1.0:
            wp_disp = self.waypoint - self._agent_state.position
            wp_dist = np.linalg.norm(wp_disp)

            # 更新进度直到到达下一个目标点
            while wp_dist < self._threshold:
                self.progress += self._step_size
                self.waypoint = self.pos_at(self.progress)
                if self.progress >= 1.0:
                    self.progress = 1.0
                    break
                wp_disp = self.waypoint - self._agent_state.position
                wp_dist = np.linalg.norm(wp_disp)

    def set_state(self, agent_state):
        self._agent_state = agent_state

    def get_target_state(self):
        # 更新目标点
        self.update_waypoint()

        previous_rigid_state = habitat_sim.RigidState(
            utils.quat_to_magnum(self._agent_state.rotation), self._agent_state.position
        )

        # TODO: Magic number
        time_step = 1.0 / 30.0

        # 追踪目标点
        self.track_waypoint(self.waypoint, previous_rigid_state, self.vel_control, dt=time_step)

        # 计算并返回目标状态
        target_rigid_state = self.vel_control.integrate_transform(time_step, previous_rigid_state)
        position = target_rigid_state.translation
        rotation = utils.quat_from_magnum(target_rigid_state.rotation)

        return position, rotation

    def track_waypoint(self, waypoint, rs, vc, dt=1.0 / 60.0):
        angular_error_threshold = 0.5
        max_linear_speed = 1.0
        max_turn_speed = 1.0

        # 计算方向向量
        glob_forward = rs.rotation.transform_vector(mn.Vector3(0, 0, -1.0)).normalized()
        glob_right = rs.rotation.transform_vector(mn.Vector3(-1.0, 0, 0)).normalized()

        # 计算到目标点的方向
        to_waypoint = mn.Vector3(waypoint) - rs.translation
        u_to_waypoint = to_waypoint.normalized()
        angle_error = float(mn.math.angle(glob_forward, u_to_waypoint))

        # 根据角度误差决定线速度
        new_velocity = 0
        if angle_error < angular_error_threshold:
            new_velocity = (vc.linear_velocity[2] - max_linear_speed) / 2.0
        else:
            new_velocity = (vc.linear_velocity[2]) / 2.0

        vc.linear_velocity = mn.Vector3(0, 0, new_velocity)

        # 角度修正部分
        rot_dir = 1.0 if mn.math.dot(glob_right, u_to_waypoint) >= 0 else -1.0
        angular_correction = 0.0
        if angle_error > (max_turn_speed * 10.0 * dt):
            angular_correction = max_turn_speed
        else:
            angular_correction = angle_error / 2.0

        vc.angular_velocity = mn.Vector3(
            0, np.clip(rot_dir * angular_correction, -max_turn_speed, max_turn_speed), 0
        )
