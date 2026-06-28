/**
 * hooks/useDetection.js — Manages the WebSocket connection to /api/detection/ws.
 *
 * The backend pushes a combined detection + alert status payload every ~0.5s.
 * This hook owns the socket lifecycle: opens when a session becomes active,
 * closes on session stop, and auto-reconnects on unexpected disconnects
 * (server restart during dev, brief network blip).
 *
 * Returns: { detectionStatus, alertActive, alertMessage, alertReason }
 * Updates via onmessage — no polling, no manual refresh needed.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { openDetectionSocket } from "../services/api";

const RECONNECT_DELAY_MS = 2_000;

const DEFAULT_DETECTION = {
  faceVisible: false,
  lookingAway: false,
  yazDeg: 0,
  pitchDeg: 0,
  zonedOutDurationSec: 0,
  gazeAlert: false,
  phoneDetected: false,
};

export function useDetection(sessionActive) {
  const [detectionStatus, setDetectionStatus] = useState(DEFAULT_DETECTION);
  const [alertActive, setAlertActive]     = useState(false);
  const [alertMessage, setAlertMessage]   = useState(null);
  const [alertReason, setAlertReason]     = useState(null);

  const socketRef   = useRef(null);
  const reconnTimer = useRef(null);
  // Track whether we should be connected at all — prevents reconnect
  // attempts after an intentional close (session stopped).
  const shouldConnectRef = useRef(false);

  const connect = useCallback(() => {
    if (!shouldConnectRef.current) return;
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const ws = openDetectionSocket();
    socketRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setDetectionStatus({
          faceVisible:          data.face_visible,
          lookingAway:          data.looking_away,
          yawDeg:               data.yaw_deg,
          pitchDeg:             data.pitch_deg,
          zonedOutDurationSec:  data.zoned_out_duration_sec,
          gazeAlert:            data.gaze_alert,
          phoneDetected:        data.phone_detected,
        });
        setAlertActive(data.alert_active);
        setAlertMessage(data.alert_message);
        setAlertReason(data.alert_reason);
      } catch (err) {
        console.error("[useDetection] Failed to parse WS message:", err);
      }
    };

    ws.onerror = () => {
      // onerror always fires just before onclose, so we handle reconnect
      // in onclose to avoid double-scheduling.
      console.warn("[useDetection] WebSocket error");
    };

    ws.onclose = () => {
      if (!shouldConnectRef.current) return;
      // Unexpected close — schedule a reconnect attempt.
      reconnTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };
  }, []);

  useEffect(() => {
    if (sessionActive) {
      shouldConnectRef.current = true;
      connect();
    } else {
      // Session stopped — close intentionally, clear reconnect timer,
      // and reset all detection + alert state to idle.
      shouldConnectRef.current = false;
      clearTimeout(reconnTimer.current);
      socketRef.current?.close();
      socketRef.current = null;
      setDetectionStatus(DEFAULT_DETECTION);
      setAlertActive(false);
      setAlertMessage(null);
      setAlertReason(null);
    }

    return () => {
      // Cleanup on unmount (e.g. hot-reload during dev)
      shouldConnectRef.current = false;
      clearTimeout(reconnTimer.current);
      socketRef.current?.close();
    };
  }, [sessionActive, connect]);

  return { detectionStatus, alertActive, alertMessage, alertReason };
}
