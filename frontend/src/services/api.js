/**
 * services/api.js — Every HTTP call to the FastAPI backend goes through here.
 *
 * Why centralized: if the backend port changes, or we add auth headers later,
 * or we switch from axios to fetch, there's one file to update — not a dozen
 * scattered component files. Components never call axios or fetch directly.
 */

import axios from "axios";

// In dev, Vite proxies /api to localhost:8000 via vite.config.js, so this
// works without CORS issues and without hard-coding the backend port in the
// frontend. In production, point this at the real API base URL.
const BASE = "/api";

const http = axios.create({
  baseURL: BASE,
  timeout: 10_000, // 10s — model loading on first session start can be slow
});

// --- Session endpoints ---

export const startSession = () => http.post("/session/start");
export const stopSession  = () => http.post("/session/stop");
export const getLiveStats = () => http.get("/session/live");
export const getHistory   = (limit = 50) => http.get(`/session/history?limit=${limit}`);
export const getSessionDetail = (id) => http.get(`/session/${id}`);

// --- Detection endpoints ---

export const getDetectionStatus = () => http.get("/detection/status");
export const dismissAlert        = () => http.post("/detection/alert/dismiss");

// --- WebSocket ---

// Returns a native WebSocket — not axios (WebSocket is not HTTP).
// The path is proxied by Vite's WS proxy during dev.
export const openDetectionSocket = () =>
  new WebSocket(`ws://${window.location.host}/api/detection/ws`);
