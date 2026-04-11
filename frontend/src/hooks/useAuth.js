// hooks/useAuth.js
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';
const TOKEN_KEY = 'nse_arena_token';

export function useAuth() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // On mount: restore token from localStorage and validate
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) {
      validateToken(stored);
    } else {
      setLoading(false);
    }
  }, []);

  const validateToken = async (tkn) => {
    try {
      const response = await axios.get(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${tkn}` },
      });
      setToken(tkn);
      setUser(response.data);
    } catch {
      // Token expired or invalid — clear it
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = useCallback(async (username, password) => {
    setError(null);
    try {
      const response = await axios.post(`${API_URL}/auth/login/json`, {
        username,
        password,
      });
      const { access_token, user: userData } = response.data;
      localStorage.setItem(TOKEN_KEY, access_token);
      setToken(access_token);
      setUser(userData);
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
      const response = await axios.post(`${API_URL}/auth/register`, {
        username,
        email,
        password,
      });
      const { access_token, user: userData } = response.data;
      localStorage.setItem(TOKEN_KEY, access_token);
      setToken(access_token);
      setUser(userData);
      return true;
    } catch (err) {
      const detail = err.response?.data?.detail || 'Registration failed';
      setError(detail);
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { token, user, loading, error, login, register, logout, clearError };
}
