"""
services/camera_service.py — Webcam feed + frame capture logic.

Why a dedicated camera worker thread: cv2.VideoCapture.read() blocks until
a frame is ready, and that blocking call must never sit anywhere near
FastAPI's async event loop. This runs entirely in its own background
thread (per the threading-over-multiprocessing decision) and just exposes
the latest frame through a lock-protected variable that the detection
service can read whenever it's ready to process one.
"""

import platform
import threading
import time
from typing import Optional

import cv2
import numpy as np

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class CameraService:
    """Owns the cv2.VideoCapture handle and a background read loop."""

    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._camera_ok = False

    def start(self) -> bool:
        """Opens the webcam and starts the background capture loop.

        Returns False if the camera couldn't be opened (e.g. already in
        use by another app, or the wrong CAMERA_INDEX) so the caller can
        surface a clear error instead of silently doing nothing.
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Camera already running — ignoring duplicate start() call")
            return self._camera_ok

        # CAP_DSHOW opens noticeably faster on Windows and avoids the
        # default MSMF backend's occasional multi-second cold-start delay.
        # It's Windows-only — fall back to letting OpenCV pick on other OSes.
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(settings.CAMERA_INDEX, backend)

        if not self._cap.isOpened():
            logger.error(f"Could not open webcam at index {settings.CAMERA_INDEX}")
            self._camera_ok = False
            return False

        self._camera_ok = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera capture thread started")
        return True

    def stop(self) -> None:
        """Signals the loop to stop and releases the camera handle."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()  # always release, even on abnormal stop
        with self._lock:
            self._latest_frame = None
        self._camera_ok = False
        logger.info("Camera capture stopped and device released")

    def _capture_loop(self) -> None:
        # Tight loop reading frames as fast as the camera provides them,
        # capped to ~30fps so this thread doesn't peg a CPU core grabbing
        # frames faster than detection could ever consume them.
        while not self._stop_event.is_set():
            ok, frame = self._cap.read()
            if not ok:
                logger.warning("Failed to read frame from webcam — retrying")
                time.sleep(0.1)
                continue
            with self._lock:
                self._latest_frame = frame
            time.sleep(0.03)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Thread-safe snapshot of the most recent frame, or None if no
        frame has been captured yet (e.g. camera just started)."""
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    @property
    def is_running(self) -> bool:
        return self._camera_ok


# Single shared instance — detection_service and the router both use this one
camera_service = CameraService()
