/**
 * components/sessionControls.jsx — Start/Stop session button + elapsed timer.
 *
 * Reads session state from StudyContext; calls context actions on click.
 * No direct API calls — that's useSession.js's job.
 */

import { useContext } from "react";
import { StudyContext } from "../App";

function formatElapsed(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function SessionControls() {
  const { sessionActive, elapsedSec, isLoading, error, startSession, stopSession } =
    useContext(StudyContext);

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Live elapsed timer — only visible while a session is running */}
      {sessionActive && (
        <div className="flex items-center gap-2">
          {/* Pulsing dot gives a subtle "recording" feel without being alarmist */}
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
          </span>
          <span className="font-mono text-3xl font-light tracking-tight text-slate-100 dark:text-slate-100">
            {formatElapsed(elapsedSec)}
          </span>
        </div>
      )}

      {/* Start / Stop button */}
      <button
        onClick={sessionActive ? stopSession : startSession}
        disabled={isLoading}
        className={[
          "relative min-w-[160px] rounded-xl px-8 py-3 text-sm font-semibold",
          "transition-all duration-150 focus:outline-none focus-visible:ring-2",
          "focus-visible:ring-amber-400/70 disabled:cursor-not-allowed disabled:opacity-50",
          sessionActive
            ? "bg-slate-700 text-slate-200 hover:bg-slate-600"
            : "bg-amber-400 text-slate-900 hover:bg-amber-300 active:scale-[0.97]",
        ].join(" ")}
      >
        {isLoading ? (
          // Inline spinner — no icon library needed
          <span className="flex items-center justify-center gap-2">
            <svg
              className="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12" cy="12" r="10"
                stroke="currentColor" strokeWidth="3"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            {sessionActive ? "Stopping…" : "Starting…"}
          </span>
        ) : sessionActive ? (
          "Stop Session"
        ) : (
          "Start Session"
        )}
      </button>

      {/* Non-intrusive error message below the button */}
      {error && (
        <p className="max-w-xs text-center text-xs text-red-400">{error}</p>
      )}

      {!sessionActive && !isLoading && (
        <p className="text-xs text-slate-500">
          Camera + detection will start automatically
        </p>
      )}
    </div>
  );
}
