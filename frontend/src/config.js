// config.js — single source of truth for the backend base URLs.
// Override locally via a .env file: VITE_API_URL=http://localhost:8010
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const WS_URL = import.meta.env.VITE_WS_URL || API_URL.replace(/^http/, 'ws') + '/ws/prices';
