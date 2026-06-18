"""
services/detection_service.py — Phone + gaze (head pose) detection ML logic.

Why MediaPipe's Tasks API instead of the old mp.solutions.face_mesh:
current MediaPipe releases no longer ship the legacy `solutions` API at
all — only `mediapipe.tasks`. The Tasks API's FaceLandmarker conveniently
also returns a facial transformation matrix per detected face, which is
MediaPipe's own head-pose estimate computed from its canonical face model.
That means we don't need to hand-roll a 6-point solvePnP setup ourselves —
we just decompose that matrix's rotation block into yaw/pitch/roll using
cv2.RQDecomp3x3 (verified against synthetic rotation matrices: angles[0]
is rotation about X = pitch, angles[1] about Y = yaw, in degrees).

Why YOLOv8n for phones instead of MediaPipe's own object detector: COCO's
"cell phone" class (index 67) via YOLOv8n is noticeably more reliable for
"phone near/in front of face" framing than MediaPipe's lightweight
EfficientDet models. We only run it every PHONE_CHECK_INTERVAL_SEC (not
every frame), so the extra inference cost is fine on CPU.

NOTE ON CALIBRATION: yaw/pitch thresholds in config.py (GAZE_YAW_THRESHOLD_DEG,
GAZE_PITCH_THRESHOLD_DEG) are reasonable starting points, not guaranteed-exact
for every webcam/face. When testing, watch the logged yaw/pitch values while
deliberately turning your head and adjust the thresholds in .env to taste.
"""

import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from ultralytics import YOLO

from config import settings
from services.camera_service import camera_service
from utils.logger import get_logger

logger = get_logger(__name__)

# Resolve model paths relative to this file's location, not the process's
# working directory — so it doesn't matter what folder `uvicorn` was
# launched from.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_MODELS_DIR = (_BACKEND_DIR / ".." / "models").resolve()
_FACE_MODEL_PATH = _MODELS_DIR / "face_landmarker.task"
_YOLO_MODEL_PATH = _MODELS_DIR / "yolov8n.pt"

# Official Google-hosted model bundle — no blendshapes variant since we
# only need the transformation matrix, which keeps the download smaller
# and inference a bit faster than the blendshapes-enabled version.
_FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

_COCO_CELL_PHONE_CLASS_ID = 67


class DetectionState:
    """Thread-safe holder for the latest detection results."""

    def __init__(self):
        self._lock = threading.Lock()
        self.face_visible = False
        self.looking_away = False
        self.yaw_deg = 0.0
        self.pitch_deg = 0.0
        self.away_since: Optional[float] = None  # epoch seconds; None if not currently away
        self.phone_detected = False

    def update_gaze(self, face_visible: bool, is_away: bool, yaw: float, pitch: float) -> None:
        with self._lock:
            self.face_visible = face_visible
            self.yaw_deg = yaw
            self.pitch_deg = pitch
            if is_away and self.away_since is None:
                self.away_since = time.time()  # mark the start of this away-streak
            elif not is_away:
                self.away_since = None  # streak broken — reset the clock
            self.looking_away = is_away

    def update_phone(self, detected: bool) -> None:
        with self._lock:
            self.phone_detected = detected

    def snapshot(self) -> dict:
        with self._lock:
            away_duration = (time.time() - self.away_since) if self.away_since else 0.0
            return {
                "face_visible": self.face_visible,
                "looking_away": self.looking_away,
                "yaw_deg": round(self.yaw_deg, 1),
                "pitch_deg": round(self.pitch_deg, 1),
                "zoned_out_duration_sec": round(away_duration, 1),
                "gaze_alert": away_duration >= settings.GAZE_ALERT_THRESHOLD_SEC,
                "phone_detected": self.phone_detected,
                "last_updated": time.time(),
            }


class DetectionService:
    def __init__(self):
        self.state = DetectionState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._face_landmarker = None
        self._yolo = None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            logger.warning("Detection already running — ignoring duplicate start() call")
            return True

        if not camera_service.start():
            return False

        try:
            self._ensure_models_loaded()
        except Exception as e:
            logger.error(f"Failed to load detection models: {e}")
            camera_service.stop()
            return False

        self.state = DetectionState()  # fresh state for this session
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._thread.start()
        logger.info("Detection thread started")
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        camera_service.stop()
        logger.info("Detection thread stopped")

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def get_status(self) -> dict:
        return self.state.snapshot()

    # ---------- model loading ----------

    def _ensure_models_loaded(self) -> None:
        # Lazy-loaded on first start() call (not at import time) so the
        # FastAPI server itself boots instantly — only paying the model
        # load cost once a session actually begins.
        if self._face_landmarker is None:
            self._download_if_missing(_FACE_MODEL_PATH, _FACE_MODEL_URL)
            logger.info("Loading MediaPipe FaceLandmarker model")
            base_options = mp_python.BaseOptions(model_asset_path=str(_FACE_MODEL_PATH))
            options = mp_vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_faces=1,
            )
            self._face_landmarker = mp_vision.FaceLandmarker.create_from_options(options)

        if self._yolo is None:
            logger.info("Loading YOLOv8n model for phone detection")
            # YOLO() auto-downloads the official weights to this exact path
            # if it doesn't already exist there — no manual download code needed.
            self._yolo = YOLO(str(_YOLO_MODEL_PATH))

    @staticmethod
    def _download_if_missing(path: Path, url: str) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading face landmarker model to {path} (first run only)...")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            raise RuntimeError(
                "Could not download the MediaPipe face landmarker model — "
                "check your internet connection and try starting the session again."
            ) from e

    # ---------- detection loop ----------

    def _detection_loop(self) -> None:
        video_timestamp_ms = 0
        last_phone_check = 0.0

        while not self._stop_event.is_set():
            frame = camera_service.get_latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            video_timestamp_ms += int(settings.DETECTION_FRAME_INTERVAL_SEC * 1000)
            self._run_gaze_check(frame, video_timestamp_ms)

            now = time.time()
            if now - last_phone_check >= settings.PHONE_CHECK_INTERVAL_SEC:
                self._run_phone_check(frame)
                last_phone_check = now

            time.sleep(settings.DETECTION_FRAME_INTERVAL_SEC)

    def _run_gaze_check(self, frame: np.ndarray, timestamp_ms: int) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._face_landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.facial_transformation_matrixes:
            # No face in frame at all (stepped away, face out of view) —
            # per spec, this counts as zoned out rather than a separate state.
            self.state.update_gaze(face_visible=False, is_away=True, yaw=0.0, pitch=0.0)
            return

        matrix = np.array(result.facial_transformation_matrixes[0]).reshape(4, 4)
        rotation = matrix[:3, :3].astype(np.float64)
        angles, *_ = cv2.RQDecomp3x3(rotation)
        pitch, yaw = float(angles[0]), float(angles[1])

        is_away = (
            abs(yaw) > settings.GAZE_YAW_THRESHOLD_DEG
            or abs(pitch) > settings.GAZE_PITCH_THRESHOLD_DEG
        )
        self.state.update_gaze(face_visible=True, is_away=is_away, yaw=yaw, pitch=pitch)

    def _run_phone_check(self, frame: np.ndarray) -> None:
        results = self._yolo.predict(
            frame,
            verbose=False,
            conf=settings.PHONE_CONFIDENCE_THRESHOLD,
            classes=[_COCO_CELL_PHONE_CLASS_ID],  # restrict inference to just this class
        )
        phone_found = len(results[0].boxes) > 0
        self.state.update_phone(phone_found)


# Single shared instance — the router calls into this
detection_service = DetectionService()
