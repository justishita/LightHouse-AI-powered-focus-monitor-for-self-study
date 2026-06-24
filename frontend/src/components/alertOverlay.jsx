/**
 * components/alertOverlay.jsx — Distraction alert popup.
 *
 * Deliberately a small corner toast, not a full-screen takeover — a study
 * tool should feel like a quiet nudge back to focus, not a surveillance
 * "you've been caught" banner. Same component/style fires for both the
 * gaze-away and phone-detected triggers (per the shared alert_service
 * design); only the message text differs, driven by `reason`.
 *
 * Controlled component: the parent (useAlerts.js, built in the frontend
 * wiring section) owns `active`/`message`/`reason` from the WebSocket
 * status stream and calls onDismiss() — which should hit
 * POST /api/detection/alert/dismiss via services/api.js — when the user
 * clicks the dismiss button. No auto-dismiss timer: it stays up until
 * the person closes it, per spec.
 */

import { useEffect, useRef } from "react";

function ReasonIcon({ reason }) {
  // Small hand-rolled line icons — keeps this component dependency-free
  // until the frontend wiring section settles on whether lucide-react (or
  // similar) gets added to the project.
  if (reason === "phone") {
    return (
      <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 stroke-amber-400" strokeWidth="1.6">
        <rect x="6" y="2" width="8" height="16" rx="1.5" />
        <path d="M9 15.2h2" strokeLinecap="round" />
      </svg>
    );
  }
  if (reason === "gaze") {
    return (
      <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 stroke-amber-400" strokeWidth="1.6">
        <path d="M2 10s2.8-5 8-5 8 5 8 5-2.8 5-8 5-8-5-8-5Z" />
        <circle cx="10" cy="10" r="2.2" />
        <path d="M3 3l14 14" strokeLinecap="round" />
      </svg>
    );
  }
  // "both" — combined signal, single dot glyph rather than two crowded icons
  return (
    <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
      <span className="absolute h-2.5 w-2.5 rounded-full bg-amber-400" />
      <span className="absolute h-2.5 w-2.5 animate-ping rounded-full bg-amber-400/70 motion-reduce:animate-none" />
    </span>
  );
}

export default function AlertOverlay({ active, message, reason, onDismiss }) {
  const dismissBtnRef = useRef(null);

  // Move focus to the dismiss button when the popup appears, and let
  // Escape close it — both expected behaviors for an interrupting alert.
  useEffect(() => {
    if (!active) return;
    dismissBtnRef.current?.focus();

    const handleKeyDown = (e) => {
      if (e.key === "Escape") onDismiss?.();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [active, onDismiss]);

  if (!active) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed right-4 top-4 z-50 w-full max-w-sm animate-[alertSlideIn_0.25s_ease-out] motion-reduce:animate-none"
    >
      <style>{`
        @keyframes alertSlideIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className="flex items-start gap-3 rounded-lg border border-slate-700/60 bg-slate-900/95 p-4 shadow-lg shadow-black/40 backdrop-blur">
        {/* Quiet amber accent bar — the one signature touch, not a wall of red */}
        <span className="absolute inset-y-0 left-0 w-1 rounded-l-lg bg-amber-400/80" aria-hidden="true" />

        <div className="mt-0.5">
          <ReasonIcon reason={reason} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Focus check
          </p>
          <p className="mt-1 text-sm leading-snug text-slate-100">{message}</p>
        </div>

        <button
          ref={dismissBtnRef}
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss alert"
          className="-m-1 shrink-0 rounded-md p-1 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
        >
          <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 stroke-current" strokeWidth="1.8">
            <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
