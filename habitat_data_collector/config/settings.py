"""Configuration constants and default values."""

# Visualization constants
TOPDOWN_METERS_PER_PIXEL = 0.05
TOPDOWN_MAP_BORDER_SIZE = 5
DEPTH_OVERLAY_SCALE = 0.2
SEMANTIC_OVERLAY_SCALE = 0.2
OVERLAY_START_X = 20
OVERLAY_START_Y = 20
OVERLAY_GAP_SIZE = 20
MAP_DISPLAY_SCALE = 0.25

# Physics and placement
GROUND_TOLERANCE = 0.3
FLOOR_HEIGHT_TOLERANCE = 0.05
BBOX_SHRINK_FACTOR = 0.7
BBOX_REDUCTION_FACTOR = 0.8
OBJECT_PLACEMENT_HEIGHT_OFFSET = 0.2
SNAP_DOWN_TARGET = -1  # habitat_sim.stage_id equivalent

# Navigation
WAYPOINT_THRESHOLD = 0.1
PATH_FILTER_TOLERANCE = 0.03
ANGULAR_ERROR_THRESHOLD = 0.5
MAX_LINEAR_SPEED = 1.0
MAX_TURN_SPEED = 1.0
PATH_FOLLOWER_STEP_SIZE = 0.01

# Map processing
MAP_SHRINK_ITERATIONS = 2
MAP_KERNEL_SIZE = 3

# Frame rate
DEFAULT_FPS = 30.0

# Recording
DEFAULT_SAVE_MODE = "timestamp"  # or "action"

# Action code mapping for action mode file naming
# File format: {frame_index:06d}_{action_code}.png
# Each frame stores the NEXT action to be executed
ACTION_CODE_MAP = {
    "move_forward": 1,   # 直行
    "turn_left": 2,      # 左转
    "turn_right": 3,     # 右转
    "move_backward": 4,  # 后退
    "look_up": 5,        # 向上看
    "look_down": 6,      # 向下看
    None: 0,             # stop / 最后一帧
}
ACTION_CODE_STOP = 0  # Used for last frame

# Display colors (BGR format for OpenCV)
COLOR_AGENT = (0, 0, 255)  # Red
COLOR_OBJECT = (0, 255, 0)  # Green
COLOR_GOAL = (255, 0, 0)    # Blue
COLOR_PATH = (0, 255, 255)  # Yellow
COLOR_REC_ACTIVE = (0, 0, 255)  # Red
COLOR_REC_INACTIVE = (169, 169, 169)  # Gray
COLOR_BORDER = (128, 128, 128)  # Gray

