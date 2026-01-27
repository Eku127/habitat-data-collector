"""ROS utility functions."""

import subprocess
from typing import Optional


def start_rosbag_recording(output_path) -> subprocess.Popen:
    """Start recording rosbag.
    
    Args:
        output_path: Path to save the rosbag file
        
    Returns:
        Process handle for the rosbag recording
    """
    topics_to_record = [
        '/camera/rgb/image_raw',
        '/camera/depth/image_raw',
        '/camera/pose',
        '/camera_info'
    ]
    
    command = ['ros2', 'bag', 'record', '-o', str(output_path)] + topics_to_record
    rosbag_process = subprocess.Popen(command)
    return rosbag_process


def stop_rosbag_recording(rosbag_process: subprocess.Popen):
    """Stop rosbag recording.
    
    Args:
        rosbag_process: Process handle for rosbag recording
    """
    if rosbag_process:
        rosbag_process.terminate()

