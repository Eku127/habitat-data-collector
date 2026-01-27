"""ROS adapter for publishing and receiving data."""

import threading
from typing import Optional, List, Tuple
import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Path
    from sensor_msgs.msg import Image, CameraInfo
    from nav_msgs.msg import Odometry
    from cv_bridge import CvBridge
    
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    Node = object  # Dummy base class


from ..utils.coordinate_transform import CoordinateTransform


if ROS_AVAILABLE:
    class DataPublisher(Node):
        """ROS node for publishing sensor data."""
        
        def __init__(self):
            super().__init__('habitat_data_publisher')
            self.bridge = CvBridge()
            
            self.rgb_pub = self.create_publisher(Image, '/camera/rgb/image_raw', 10)
            self.depth_pub = self.create_publisher(Image, '/camera/depth/image_raw', 10)
            self.pose_pub = self.create_publisher(Odometry, '/camera/pose', 10)
            self.camera_info_pub = self.create_publisher(CameraInfo, '/camera_info', 10)
        
        def publish_rgb(self, rgb_img: np.ndarray):
            """Publish RGB image."""
            rgb_img_bgr = rgb_img[:, :, [2, 1, 0]]
            ros_img = self.bridge.cv2_to_imgmsg(rgb_img_bgr, encoding="bgr8")
            ros_img.header.stamp = self.get_clock().now().to_msg()
            self.rgb_pub.publish(ros_img)
        
        def publish_depth(self, depth_img: np.ndarray):
            """Publish depth image."""
            depth_img_mm = (depth_img * 1000).astype(np.uint16)
            ros_depth = self.bridge.cv2_to_imgmsg(depth_img_mm, encoding="16UC1")
            ros_depth.header.stamp = self.get_clock().now().to_msg()
            self.depth_pub.publish(ros_depth)
        
        def publish_pose(self, pose: List[float]):
            """Publish camera pose as Odometry."""
            odom_msg = Odometry()
            odom_msg.header.stamp = self.get_clock().now().to_msg()
            odom_msg.header.frame_id = 'map'
            odom_msg.child_frame_id = 'camera'
            
            odom_msg.pose.pose.position.x = pose[0]
            odom_msg.pose.pose.position.y = pose[1]
            odom_msg.pose.pose.position.z = pose[2]
            odom_msg.pose.pose.orientation.x = pose[3]
            odom_msg.pose.pose.orientation.y = pose[4]
            odom_msg.pose.pose.orientation.z = pose[5]
            odom_msg.pose.pose.orientation.w = pose[6]
            
            self.pose_pub.publish(odom_msg)
        
        def publish_camera_info(self, fx: float, fy: float, cx: float, cy: float, 
                               width: int, height: int):
            """Publish camera intrinsics."""
            camera_info_msg = CameraInfo()
            camera_info_msg.width = width
            camera_info_msg.height = height
            camera_info_msg.k = [float(fx), 0.0, float(cx), 
                                0.0, float(fy), float(cy), 
                                0.0, 0.0, 1.0]
            camera_info_msg.p = [float(fx), 0.0, float(cx), 0.0, 
                                0.0, float(fy), float(cy), 0.0, 
                                0.0, 0.0, 1.0, 0.0]
            
            camera_info_msg.header.stamp = self.get_clock().now().to_msg()
            camera_info_msg.header.frame_id = 'camera_frame'
            
            self.camera_info_pub.publish(camera_info_msg)
    
    
    class PathListener(Node):
        """ROS node for listening to navigation paths."""
        
        def __init__(self):
            super().__init__('habitat_path_listener')
            self.latest_path = None
            
            self.path_subscriber = self.create_subscription(
                Path,
                '/action_path',
                self.path_callback,
                10
            )
            
            self.get_logger().info("Path listener initialized")
        
        def path_callback(self, msg: Path):
            """Callback for path messages."""
            current_path = [
                (pose.pose.position.x, pose.pose.position.y, pose.pose.position.z)
                for pose in msg.poses
            ]
            
            # Transform to Habitat coordinates
            current_path = CoordinateTransform.transform_path_to_habitat(current_path)
            
            if self.latest_path != current_path:
                self.latest_path = current_path
                self.get_logger().info(f"Received path with {len(current_path)} points")
        
        def get_latest_path(self) -> Optional[List[Tuple[float, float, float]]]:
            """Get the latest received path."""
            return self.latest_path


class ROSAdapter:
    """Adapter for ROS integration."""
    
    def __init__(self, cfg):
        """Initialize ROS adapter.
        
        Args:
            cfg: Configuration
        """
        if not ROS_AVAILABLE:
            raise ImportError("ROS 2 not available")
        
        self.cfg = cfg
        
        # Initialize ROS
        rclpy.init()
        
        self.publisher = DataPublisher()
        self.listener = PathListener()
        
        # Run listener in separate thread
        self.ros_thread = threading.Thread(
            target=lambda: rclpy.spin(self.listener),
            daemon=True
        )
        self.ros_thread.start()
        
        print("ROS adapter ready")
    
    def publish_data(self, simulator, observations):
        """Publish sensor data to ROS.
        
        Args:
            simulator: Simulator service
            observations: Sensor observations
        """
        if "color_sensor" in observations:
            self.publisher.publish_rgb(np.array(observations["color_sensor"]))
        
        if "depth_sensor" in observations:
            self.publisher.publish_depth(np.array(observations["depth_sensor"]))
        
        pose = simulator.get_agent_pose()
        self.publisher.publish_pose(pose)
        
        fx, fy, cx, cy, width, height = simulator.get_camera_intrinsics("color_sensor")
        self.publisher.publish_camera_info(fx, fy, cx, cy, width, height)
    
    def get_global_path(self) -> Optional[List[Tuple[float, float, float]]]:
        """Get latest global path from ROS."""
        return self.listener.get_latest_path()
    
    def shutdown(self):
        """Shutdown ROS."""
        if ROS_AVAILABLE:
            rclpy.shutdown()

