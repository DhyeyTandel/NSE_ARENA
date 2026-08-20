// config.js — single source of truth for the backend base URLs.
// Override locally via a .env file: VITE_API_URL=http://localhost:8010
// An explicitly empty VITE_API_URL (as set by the Docker Compose frontend
// build) means "same origin" — requests go out as relative paths, which
// Caddy then routes to the backend. `??` (not `||`) so that empty string
// is honored instead of falling through to the localhost default.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
export const WS_URL = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws') + '/ws/prices';
