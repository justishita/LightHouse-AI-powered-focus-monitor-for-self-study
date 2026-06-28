/**
 * hooks/useAlerts.js — Alert dismiss logic.
 *
 * Deliberately thin: the alert state itself lives in useDetection (it comes
 * from the WebSocket). This hook's only job is providing a dismiss() action
 * that calls the backend and lets the WS update clear the state on its next
 * push — so we don't need optimistic local state updates or manual syncing.
 */

import { useCallback, useState } from "react";
import { dismissAlert as dismissAlertApi } from "../services/api";

export function useAlerts() {
  const [isDismissing, setIsDismissing] = useState(false);

  const dismiss = useCallback(async () => {
    if (isDismissing) return; // prevent double-tap
    setIsDismissing(true);
    try {
      await dismissAlertApi();
      // No need to manually clear alertActive here — the WS push every
      // ~0.5s will carry the updated state (alert_active: false) within
      // half a second of the dismiss landing on the server.
    } catch (err) {
      console.error("[useAlerts] dismiss failed:", err);
    } finally {
      setIsDismissing(false);
    }
  }, [isDismissing]);

  return { dismiss, isDismissing };
}
