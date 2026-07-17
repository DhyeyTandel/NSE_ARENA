// hooks/useAuth.js
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_URL } from '../config';

// Auth lives in an httpOnly cookie set by the backend — JS never sees the
// token (closes the XSS-token-theft hole of localStorage). Every request
// needs credentials so the browser attaches the cookie, and mutating
// requests need X-Requested-With as the CSRF guard the backend enforces.
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: { 'X-Requested-With': 'XMLHttpRequest' },
});

export function useAuth() {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // On mount: the cookie (if present) authenticates /auth/me
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const response = await api.get('/auth/me');
        setAuthenticated(true);
        setUser(response.data);
      } catch {
        setAuthenticated(false);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    restoreSession();
  }, []);

  const login = useCallback(async (username, password) => {
    setError(null);
    try {
      const response = await api.post('/auth/login/json', { username, password });
      setAuthenticated(true);
      setUser(response.data.user);
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Login failed';
      setError(detail);
      return false;
    }
  }, []);

  const register = useCallback(async (username, email, password) => {
    setError(null);
    try {
      const response = await api.post('/auth/register', { username, email, password });
      setAuthenticated(true);
      setUser(response.data.user);
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Registration failed';
      setError(detail);
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Cookie clearing failed server-side; still drop local state
    }
    setAuthenticated(false);
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { authenticated, user, loading, error, login, register, logout, clearError };
}
