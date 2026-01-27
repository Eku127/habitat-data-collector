# ROS Integration Documentation

## ROS2 Topic Configuration

In this project, ROS topics are configured directly in the code. To modify the topic names or types, users should edit the relevant sections in `adapters/ros_adapter.py`.

The ROS publishers are defined in the `DataPublisher` class as follows:

```python
class DataPublisher(Node):
    def __init__(self):
        super().__init__('habitat_data_publisher')
        self.bridge = CvBridge()

        self.rgb_pub = self.create_publisher(Image, '/camera/rgb/image_raw', 10)
        self.depth_pub = self.create_publisher(Image, '/camera/depth/image_raw', 10)
        self.pose_pub = self.create_publisher(Odometry, '/camera/pose', 10)
        self.camera_info_pub = self.create_publisher(CameraInfo, '/camera_info', 10)
```

Topic names and message types are defined in this section of the code and should be modified as necessary. All functionality is implemented in **ROS2**.

## ROS1 Bridge

This section describes how to set up the ROS1-ROS2 bridge on Ubuntu 22.04 to facilitate the conversion of ROS2 topics to ROS1 topics, ensuring compatibility with simulators that use ROS1.

> ⚠️ This section is under development
