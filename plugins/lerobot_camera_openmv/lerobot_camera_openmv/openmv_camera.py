import logging
import threading
import time
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import ColorMode

from .config_openmv import OpenMVCameraConfig

logger = logging.getLogger(__name__)

# Runs on the camera. Every image-forming setting is pinned; the stream channel
# delivers the latest snapshot to the host.
DEVICE_SCRIPT = """
import csi
c = csi.CSI()
c.reset()
c.pixformat(csi.RGB565)
c.framesize(csi.{framesize})
c.snapshot(time={warmup_ms})
c.auto_gain(False, gain_db={gain_db})
c.auto_exposure(False, exposure_us={exposure_us})
{whitebal}
c.snapshot(time=200)
print("OMV_SETTINGS", c.exposure_us(), c.gain_db(), c.rgb_gain_db(), c.width(), c.height())
while True:
    c.snapshot()
"""


class OpenMVCamera(Camera):
    """LeRobot ``Camera`` backed by an OpenMV board.

    A background thread pulls frames from the device stream and keeps the most recent
    one, so ``async_read`` and ``read_latest`` never block on USB round trips.
    """

    def __init__(self, config: OpenMVCameraConfig):
        super().__init__(config)
        self.config = config
        self._cam = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._new_frame = threading.Event()
        self._frame: NDArray[Any] | None = None
        self._frame_ts = 0.0
        self._error: Exception | None = None
        self.device_settings: str | None = None

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.config.port})"

    @property
    def is_connected(self) -> bool:
        return self._cam is not None and self._thread is not None and self._thread.is_alive()

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        import serial.tools.list_ports

        return [
            {"name": p.description, "type": "OpenMV", "id": p.device, "serial": p.serial_number}
            for p in serial.tools.list_ports.comports()
            if p.vid == 0x37C5
        ]

    def _script(self) -> str:
        if self.config.rgb_gain_db is None:
            whitebal = "c.auto_whitebal(False)"
        else:
            r, g, b = self.config.rgb_gain_db
            whitebal = f"c.auto_whitebal(False, rgb_gain_db=({r}, {g}, {b}))"
        return DEVICE_SCRIPT.format(
            framesize=self.config.framesize,
            warmup_ms=int(self.config.warmup_s * 1000),
            gain_db=self.config.gain_db,
            exposure_us=self.config.exposure_us,
            whitebal=whitebal,
        )

    def connect(self, warmup: bool = True) -> None:
        if self.is_connected:
            raise RuntimeError(f"{self} is already connected")
        from openmv import Camera as OMVCamera

        cam = OMVCamera(self.config.port, timeout=2.0, max_payload=self.config.max_payload)
        cam.connect()
        # A script left running from a previous session prints a KeyboardInterrupt
        # traceback when stopped. Stop it and drain stdout so that only output from
        # this session is checked for errors.
        try:
            cam.stop()
        except Exception:
            pass
        time.sleep(0.5)
        cam.read_stdout()
        cam.exec(self._script())
        time.sleep(self.config.warmup_s + 0.5)
        out = cam.read_stdout() or ""
        for line in out.splitlines():
            if line.startswith("OMV_SETTINGS"):
                self.device_settings = line
                logger.info("%s %s", self, line)
        if "Traceback" in out or "Error" in out or self.device_settings is None:
            cam.stop()
            cam.disconnect()
            raise RuntimeError(f"{self} device script failed:\n{out}")
        cam.streaming(True)
        self._cam = cam
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, name=f"{self}_reader", daemon=True)
        self._thread.start()
        if warmup:
            frame = self.async_read(timeout_ms=3000)
            if frame.shape[:2] != (self.config.height, self.config.width):
                self.disconnect()
                raise RuntimeError(
                    f"{self} produced {frame.shape[1]}x{frame.shape[0]}, "
                    f"expected {self.config.width}x{self.config.height}"
                )

    def _reader(self) -> None:
        bgr = self.config.color_mode == ColorMode.BGR
        while not self._stop.is_set():
            try:
                f = self._cam.read_frame()
            except Exception as e:  # surface transport errors to the caller
                self._error = e
                logger.exception("%s reader stopped", self)
                return
            if f is None:
                time.sleep(0.002)
                continue
            w, h = f["width"], f["height"]
            img = np.frombuffer(f["data"], dtype=np.uint8)[: w * h * 3].reshape(h, w, 3)
            if bgr:
                img = img[:, :, ::-1]
            with self._lock:
                self._frame = img.copy()
                self._frame_ts = time.perf_counter()
            self._new_frame.set()

    def _check(self) -> None:
        if self._error is not None:
            raise RuntimeError(f"{self} stream failed: {self._error}")
        if not self.is_connected:
            raise RuntimeError(f"{self} is not connected")

    def async_read(self, timeout_ms: float = 200) -> NDArray[Any]:
        self._check()
        if not self._new_frame.wait(timeout_ms / 1000):
            self._check()
            raise TimeoutError(f"{self}: no new frame within {timeout_ms} ms")
        with self._lock:
            frame = self._frame
            self._new_frame.clear()
        return frame

    def read(self) -> NDArray[Any]:
        return self.async_read(timeout_ms=1000)

    def read_latest(self, max_age_ms: int = 500) -> NDArray[Any]:
        self._check()
        with self._lock:
            frame, ts = self._frame, self._frame_ts
        if frame is None:
            raise RuntimeError(f"{self} has not captured any frame yet")
        age_ms = (time.perf_counter() - ts) * 1000
        if age_ms > max_age_ms:
            raise TimeoutError(f"{self}: latest frame is {age_ms:.0f} ms old")
        return frame

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._cam is not None:
            try:
                self._cam.streaming(False)
                self._cam.stop()
            except Exception:
                pass
            try:
                self._cam.disconnect()
            except Exception:
                pass
        self._cam = None
        self._thread = None
