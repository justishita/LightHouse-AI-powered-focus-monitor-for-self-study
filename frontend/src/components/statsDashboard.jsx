/**
 * components/statsDashboard.jsx — Focus score ring, live stats, and history.
 *
 * Three sections:
 *   1. Live stats (visible during an active session): focus % ring, streak,
 *      distraction count, phone/gaze status indicators
 *   2. Last session summary (shown immediately after stop)
 *   3. History table (all completed sessions, newest first)
 *
 * All data comes from StudyContext — no direct API calls here.
 */

import { useContext, useEffect, useState } from "react";
import { StudyContext } from "../App";
import { getHistory } from "../services/api";

// --- Focus score ring (SVG, no chart library) ---
// Circumference of a circle with r=45: 2π×45 ≈ 283px.
// We animate stroke-dashoffset from 283 (empty) to 283 - (score/100 × 283).
const CIRCUMFERENCE = 283;

function FocusRing({ score }) {
  const offset = CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE;
  const color =
    score >= 80 ? "#4ade80"   // green-400
    : score >= 50 ? "#FBBF24" // amber-400
    : "#f87171";              // red-400

  return (
    <div className="relative flex h-36 w-36 items-center justify-center">
      <svg className="absolute -rotate-90" viewBox="0 0 100 100">
        {/* Background track */}
        <circle
          cx="50" cy="50" r="45"
          fill="none"
          stroke="currentColor"
          strokeWidth="7"
          className="text-slate-700"
        />
        {/* Filled arc — animates in on mount via the keyframe in index.css */}
        <circle
          cx="50" cy="50" r="45"
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.4s ease" }}
        />
      </svg>
      <div className="flex flex-col items-center">
        <span className="text-2xl font-bold text-slate-100">{Math.round(score)}%</span>
        <span className="text-[10px] uppercase tracking-wider text-slate-400">Focus</span>
      </div>
    </div>
  );
}

// --- Small stat card ---
function StatCard({ label, value, sub }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/50 px-5 py-4">
      <span className="text-xl font-semibold text-slate-100">{value}</span>
      <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
      {sub && <span className="text-[10px] text-slate-500">{sub}</span>}
    </div>
  );
}

// --- History table ---
function formatDate(epochSec) {
  return new Date(epochSec * 1000).toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatDuration(sec) {
  if (!sec) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function HistoryTable({ rows = [] }) {
  if (!Array.isArray(rows) || !rows.length)
    return (
      <p className="py-6 text-center text-sm text-slate-500">
        No completed sessions yet.
      </p>
    );

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/60">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-700/60 bg-slate-800/50">
          <tr>
            {["Date", "Duration", "Focus", "Max Streak", "Distractions"].map((h) => (
              <th key={h} className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/40">
          {rows.map((s) => (
            <tr key={s.id} className="transition-colors hover:bg-slate-800/30">
              <td className="px-4 py-3 text-slate-300">{formatDate(s.started_at)}</td>
              <td className="px-4 py-3 text-slate-300">{formatDuration(s.duration_sec)}</td>
              <td className="px-4 py-3">
                <span className={
                  s.focus_score >= 80 ? "text-green-400"
                  : s.focus_score >= 50 ? "text-amber-400"
                  : "text-red-400"
                }>
                  {s.focus_score != null ? `${Math.round(s.focus_score)}%` : "—"}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-300">
                {s.max_streak_sec != null ? formatDuration(s.max_streak_sec) : "—"}
              </td>
              <td className="px-4 py-3 text-slate-300">{s.distraction_count ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Main component ---
export default function StatsDashboard() {
  const { sessionActive, liveStats } = useContext(StudyContext);
  const [history, setHistory] = useState([]);

  // Fetch history on mount and whenever a session ends
  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await getHistory();
        setHistory(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("[StatsDashboard] history fetch failed:", err);
      }
    };
    load();
  }, [sessionActive]); // re-fetch when sessionActive flips to false (session just stopped)

  const stats = liveStats;

  return (
    <div className="flex flex-col gap-8">
      {/* Live stats — only during an active session */}
      {sessionActive && stats && (
        <section>
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Live
          </h2>
          <div className="flex flex-wrap items-center gap-6">
            <FocusRing score={stats.focus_score ?? 100} />
            <div className="flex flex-wrap gap-3">
              <StatCard
                label="Current Streak"
                value={`${stats.current_streak_min?.toFixed(1) ?? "0.0"} min`}
              />
              <StatCard
                label="Best Streak"
                value={`${stats.max_streak_min?.toFixed(1) ?? "0.0"} min`}
              />
              <StatCard
                label="Alerts Fired"
                value={stats.distraction_count ?? 0}
                sub="this session"
              />
            </div>
          </div>
        </section>
      )}

      {/* History table — always visible */}
      <section>
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Session History
        </h2>
        <HistoryTable rows={history} />
      </section>
    </div>
  );
}