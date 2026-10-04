"""LeRobot camera plugin for OpenMV boards.

LeRobot imports packages whose distribution name starts with ``lerobot_camera_`` at
startup (``register_third_party_plugins``). Importing this package registers the
``openmv`` camera type and exposes the device class that LeRobot resolves from the
config class name (``OpenMVCameraConfig`` -> ``OpenMVCamera``).
"""
from .config_openmv import OpenMVCameraConfig
from .openmv_camera import OpenMVCamera

__all__ = ["OpenMVCameraConfig", "OpenMVCamera"]
