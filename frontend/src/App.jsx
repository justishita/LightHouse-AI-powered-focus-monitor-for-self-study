/**
 * App.jsx — Root component. Owns StudyContext and the overall page layout.
 *
 * Why context lives here rather than in a separate context file: for an
 * app of this scale (one page, four components), the extra indirection of
 * a separate context/provider file adds navigation overhead without adding
 * clarity. If the app grows to multiple routes, extract it then.
 *
 * StudyContext is exported so components can import it without a circular
 * dependency (they import from App, not from a provider that imports them).
 */

import { createContext, useCallback, useEffect, useState } from "react";
import AlertOverlay from "./components/alertOverlay";
import SessionControls from "./components/sessionControls";
import StatsDashboard from "./components/statsDashboard";
import { useAlerts } from "./hooks/useAlerts";
import { useDetection } from "./hooks/useDetection";
import { useSession } from "./hooks/useSession";
import './styles/index.css'

export const StudyContext = createContext(null);

// Dark mode: read system preference on first load, then allow manual toggle.
// Stored in localStorage so the choice survives a page refresh.
function getInitialDarkMode() {
  const stored = localStorage.getItem("selfstudy-dark");
  if (stored !== null) return stored === "true";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function App() {
  const [darkMode, setDarkMode] = useState(getInitialDarkMode);

  // Apply/remove "dark" class on <html> whenever darkMode changes.
  // Tailwind's darkMode:"class" strategy reads this class.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
    localStorage.setItem("selfstudy-dark", darkMode);
  }, [darkMode]);

  const toggleDarkMode = useCallback(
    () => setDarkMode((d) => !d),
    []
  );

  const session   = useSession();
  const detection = useDetection(session.sessionActive);
  const alerts    = useAlerts();

  const ctx = {
    // Session
    sessionActive: session.sessionActive,
    sessionId:     session.sessionId,
    elapsedSec:    session.elapsedSec,
    liveStats:     session.liveStats,
    isLoading:     session.isLoading,
    error:         session.error,
    startSession:  session.start,
    stopSession:   session.stop,
    // Detection
    detectionStatus: detection.detectionStatus,
    // Alert
    alertActive:   detection.alertActive,
    alertMessage:  detection.alertMessage,
    alertReason:   detection.alertReason,
    dismissAlert:  alerts.dismiss,
    // UI
    darkMode,
    toggleDarkMode,
  };

  return (
    <StudyContext.Provider value={ctx}>
      {/* Alert popup renders on top of everything, fixed to the corner */}
      <AlertOverlay
        active={detection.alertActive}
        message={detection.alertMessage}
        reason={detection.alertReason}
        onDismiss={alerts.dismiss}
      />

      {/* Page shell */}
      <div className="min-h-screen bg-white dark:bg-slate-950 transition-colors duration-200">

        {/* Header */}
        <header className="border-b border-slate-200 dark:border-slate-800 px-6 py-4">
          <div className="mx-auto flex max-w-4xl items-center justify-between">
            <div className="flex items-center gap-2.5">
              {/* Simple eye-with-book logo mark — inline SVG, no assets needed */}
              <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-amber-400">
                <path
                  d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"
                  stroke="currentColor" strokeWidth="1.8"
                />
                <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.8" />
              </svg>
              <span className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                SelfStudy
              </span>
            </div>

            {/* Dark mode toggle */}
            <button
              onClick={toggleDarkMode}
              aria-label="Toggle dark mode"
              className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              {darkMode ? (
                // Sun icon
                <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 stroke-current" strokeWidth="1.8">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeLinecap="round" />
                </svg>
              ) : (
                // Moon icon
                <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 stroke-current" strokeWidth="1.8">
                  <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79Z" strokeLinecap="round" />
                </svg>
              )}
            </button>
          </div>
        </header>

        {/* Main content */}
        <main className="mx-auto max-w-4xl px-6 py-10 flex flex-col gap-10">

          {/* Hero / session start area */}
          <section className="flex flex-col items-center gap-2 text-center">
            {!session.sessionActive && (
              <p className="mb-2 text-sm text-slate-400 dark:text-slate-500">
                Stay focused. We'll let you know if you drift.
              </p>
            )}
            <SessionControls />
          </section>

          {/* Stats and history */}
          <StatsDashboard />
        </main>
      </div>
    </StudyContext.Provider>
  );
}

