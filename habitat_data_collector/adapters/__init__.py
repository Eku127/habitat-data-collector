"""Adapters module for external integrations."""

try:
    from .ros_adapter import ROSAdapter
    __all__ = ["ROSAdapter"]
except ImportError:
    # ROS not available
    __all__ = []

