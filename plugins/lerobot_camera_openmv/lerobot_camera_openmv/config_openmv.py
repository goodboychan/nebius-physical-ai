from dataclasses import dataclass

from lerobot.cameras.configs import CameraConfig, ColorMode

# OpenMV framesize name -> (width, height) produced by the PAG7936 sensor on the AE3.
# The sensor is 16:10, so "VGA" yields 640x400 and "QVGA" yields 320x200.
FRAMESIZES = {"QVGA": (320, 200), "VGA": (640, 400)}


@CameraConfig.register_subclass("openmv")
@dataclass
class OpenMVCameraConfig(CameraConfig):
    """OpenMV camera streamed over the OpenMV Protocol V2.

    All image-forming settings are fixed on the device so that frames recorded during
    data collection and frames seen at deployment come from identical sensor settings.

    Attributes:
        port: Serial device of the camera (a udev symlink is recommended).
        framesize: OpenMV framesize name, see ``FRAMESIZES``.
        exposure_us: Fixed exposure time in microseconds (auto exposure is disabled).
        gain_db: Fixed analog gain in dB (auto gain is disabled).
        rgb_gain_db: Fixed white-balance gains (R, G, B) in dB. If None, auto white
            balance runs for ``warmup_s`` and is then frozen; the frozen values are
            logged so they can be pinned here for later sessions.
        warmup_s: Seconds the camera settles before streaming starts.
        max_payload: Protocol packet payload size in bytes.
    """

    port: str = "/dev/so101_cam_wrist_omv"
    framesize: str = "QVGA"
    # Defaults are the values calibrated for the SO-101 wrist camera on 2026-10-04
    # (night, room lighting only): exposure/gain from a sweep with a can in view,
    # white balance from white paper filling the frame (R/G 0.99, B/G 0.98).
    exposure_us: int = 10000
    gain_db: float = 18.0
    rgb_gain_db: tuple[float, float, float] | None = (4.67, 0.0, 4.39)
    color_mode: ColorMode = ColorMode.RGB
    warmup_s: float = 2.0
    max_payload: int = 32768

    def __post_init__(self) -> None:
        if self.framesize not in FRAMESIZES:
            raise ValueError(f"framesize must be one of {sorted(FRAMESIZES)}, got {self.framesize!r}")
        width, height = FRAMESIZES[self.framesize]
        if self.width is None:
            self.width = width
        if self.height is None:
            self.height = height
        if (self.width, self.height) != (width, height):
            raise ValueError(
                f"framesize {self.framesize} produces {width}x{height}, "
                f"but width/height were set to {self.width}x{self.height}"
            )
        if self.color_mode not in (ColorMode.RGB, ColorMode.BGR):
            raise ValueError(f"color_mode must be RGB or BGR, got {self.color_mode}")
