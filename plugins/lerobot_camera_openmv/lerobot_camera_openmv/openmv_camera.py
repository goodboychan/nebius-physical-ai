import atexit
import logging
import os
import subprocess
import threading
import time
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import ColorMode

from .config_openmv import OpenMVCameraConfig

logger = logging.getLogger(__name__)


class _DropOpenMVChatter(logging.Filter):
    """openmv 패키지는 루트 로거에 프레임마다 INFO("Frame Ready")를 찍는다. 녹화 터미널을 덮으므로 INFO 이하만 버린다."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.levelno <= logging.INFO and "/openmv/" in record.pathname.replace("\\", "/"))


def _install_log_filter() -> None:
    root = logging.getLogger()
    for h in root.handlers:
        if not any(isinstance(f, _DropOpenMVChatter) for f in h.filters):
            h.addFilter(_DropOpenMVChatter())

def _patch_serial_write_timeout(seconds: float = 2.0) -> None:
    """openmv은 pyserial을 읽기 timeout만 주고 연다. 보드 링크가 멈추면 write()가 영원히 막혀
    녹화 프로세스가 연결 단계에서 멈춘다(2026-10-06). 쓰기에도 timeout을 걸어 예외로 바꾼다."""
    import openmv.camera as oc
    import serial

    if getattr(oc.serial, "_so101_patched", False):
        return

    class _Shim:
        _so101_patched = True

        def __getattr__(self, name):
            return getattr(serial, name)

        @staticmethod
        def Serial(*args, **kwargs):  # noqa: N802
            kwargs.setdefault("write_timeout", seconds)
            return serial.Serial(*args, **kwargs)

    oc.serial = _Shim()


def _usb_reauthorize(port: str) -> bool:
    """보드를 USB 단에서 끊었다 다시 붙인다(뽑았다 꽂기와 같음). sudo 비밀번호 없이 될 때만 동작."""
    try:
        tty = os.path.basename(os.path.realpath(port))
        usbdev = os.path.dirname(os.path.realpath(f"/sys/class/tty/{tty}/device"))
        auth = os.path.join(usbdev, "authorized")
        for v in ("0", "1"):
            subprocess.run(["sudo", "-n", "tee", auth], input=v.encode(), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=5)
            time.sleep(1.0)
    except Exception as e:  # noqa: BLE001
        logger.warning("USB re-authorize failed for %s: %s", port, e)
        return False
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not os.path.exists(port):
        time.sleep(0.5)
    time.sleep(3.0)  # 열거 직후에는 EIO가 난다
    return True


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

    def _open_fresh(self):
        # 링크가 막혔을 때 영원히 멈추지 않고 에러로 끝나게 한다. 복구는 scripts/so101_omv_recover.sh.
        _patch_serial_write_timeout()
        return self._open_fresh_once()

    def _open_fresh_once(self):
        """Open the camera with a clean interpreter state.

        On firmware 5.0.1 the protocol link stalls after ``stop()`` and sometimes after
        a session that ended abruptly. Rebooting the board (``reset()``) and reconnecting
        after it re-enumerates is the reliable way to start every session from the same
        state; it costs a few seconds per connect.
        """
        from openmv import Camera as OMVCamera

        def open_once():
            cam = OMVCamera(self.config.port, timeout=2.0, max_payload=self.config.max_payload)
            cam.connect()
            return cam

        try:
            cam = open_once()
        except Exception as e:
            raise RuntimeError(
                f"{self} could not synchronize with the board ({e}). Unplug and replug the camera."
            ) from e
        try:
            cam.reset()
        except Exception:
            pass
        try:
            cam.disconnect()
        except Exception:
            pass
        deadline = time.monotonic() + 20
        while True:
            time.sleep(1.0)
            try:
                cam = open_once()
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise RuntimeError(f"{self} did not come back after reset")
        # After the reboot the board runs its stored main.py; exec() does not preempt it.
        # Stop it, then resynchronize (the link stalls right after stop()).
        cam.stop()
        cam.disconnect()
        time.sleep(0.5)
        return open_once()

    def connect(self, warmup: bool = True) -> None:
        if self.is_connected:
            raise RuntimeError(f"{self} is already connected")
        _install_log_filter()
        # LeRobot은 모터 버스를 먼저 끊고 카메라를 끊는다. 버스에서 에러가 나면(집게 과부하 등) 카메라
        # disconnect가 불리지 않아 보드가 스트리밍 중인 채로 남고, 다음 연결이 막힌다. 종료 시 항상 정리한다.
        atexit.register(self.disconnect)
        cam = self._open_fresh()
        cam.read_stdout()
        cam.exec(self._script())
        # Wait for the settings line instead of a fixed sleep: the device warmup plus the
        # interpreter start after a reset takes a variable amount of time.
        out = ""
        deadline = time.monotonic() + self.config.warmup_s + 6
        while "OMV_SETTINGS" not in out and "Traceback" not in out and time.monotonic() < deadline:
            time.sleep(0.2)
            out += cam.read_stdout() or ""
        for line in out.splitlines():
            if line.startswith("OMV_SETTINGS"):
                self.device_settings = line
                logger.info("%s %s", self, line)
        if "Traceback" in out or "Error" in out or self.device_settings is None:
            try:
                cam.disconnect()
            except Exception:
                pass
            raise RuntimeError(f"{self} device script failed:\n{out}")
        cam.streaming(True)
        self._cam = cam
        self._error = None
        self._stop.clear()
        self._new_frame.clear()
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
        if self._cam is None and self._thread is None:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._cam is not None:
            # Do not call stop(): it stalls the link on firmware 5.0.1. The next connect()
            # reboots the board anyway.
            try:
                self._cam.streaming(False)
            except Exception:
                pass
            try:
                self._cam.disconnect()
            except Exception:
                pass
        self._cam = None
        self._thread = None
