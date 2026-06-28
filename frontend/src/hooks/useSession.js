/**
 * hooks/useSession.js — Session lifecycle, elapsed timer, live stats polling.
 *
 * Separating this from useDetection so each hook does exactly one thing:
 * this hook knows about sessions and stats; useDetection knows about sockets.
 *
 * Live stats are polled every SESSION_POLL_MS rather than pushed over WS
 * because they change slowly (second-level granularity) — polling is
 * simpler and doesn't need a second WebSocket connection.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getLiveStats, startSession, stopSession } from "../services/api";

const SESSION_POLL_MS = 5_000; // poll live stats every 5 seconds

export function useSession() {
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionId, setSessionId]         = useState(null);
  const [elapsedSec, setElapsedSec]       = useState(0);
  const [liveStats, setLiveStats]         = useState(null);
  const [isLoading, setIsLoading]         = useState(false);
  const [error, setError]                 = useState(null);

  const elapsedTimer = useRef(null);
  const pollTimer    = useRef(null);
  const startedAt    = useRef(null);

  // --- Elapsed timer (runs locally in JS, not from the server) ---
  // Why local: the server's elapsed_sec updates every tick interval (1s),
  // but we want a smooth per-second counter in the UI without waiting for
  // the next poll. The server is the source of truth for the stored value;
  // this is just display sugar.
  const startElapsedTimer = useCallback(() => {
    startedAt.current = Date.now();
    elapsedTimer.current = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt.current) / 1000));
    }, 1000);
  }, []);

  const stopElapsedTimer = useCallback(() => {
    clearInterval(elapsedTimer.current);
    setElapsedSec(0);
    startedAt.current = null;
  }, []);

  // --- Live stats polling ---
  const startPolling = useCallback(() => {
    const poll = async () => {
      try {
        const { data } = await getLiveStats();
        if (data.active) setLiveStats(data);
      } catch {
        // Swallow polling errors — a transient network blip shouldn't
        // surface an error state just because the stats didn't refresh.
      }
    };
    poll(); // immediate first fetch
    pollTimer.current = setInterval(poll, SESSION_POLL_MS);
  }, []);

  const stopPolling = useCallback(() => {
    clearInterval(pollTimer.current);
    setLiveStats(null);
  }, []);

  // --- Session actions ---
  const start = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await startSession();
      if (!data.ok) {
        setError(data.error ?? "Could not start session.");
        return;
      }
      setSessionId(data.session_id);
      setSessionActive(true);
      startElapsedTimer();
      startPolling();
    } catch (err) {
      setError("Backend unreachable — is the server running?");
      console.error("[useSession] start error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [startElapsedTimer, startPolling]);

  const stop = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await stopSession();
    } catch (err) {
      console.error("[useSession] stop error:", err);
    } finally {
      setSessionActive(false);
      setSessionId(null);
      stopElapsedTimer();
      stopPolling();
      setIsLoading(false);
    }
  }, [stopElapsedTimer, stopPolling]);

  // Cleanup on unmount (handles hot-reload during dev)
  useEffect(() => {
    return () => {
      clearInterval(elapsedTimer.current);
      clearInterval(pollTimer.current);
    };
  }, []);

  return {
    sessionActive,
    sessionId,
    elapsedSec,
    liveStats,
    isLoading,
    error,
    start,
    stop,
  };
}
