// hooks/useLeaderboard.js
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

export function useLeaderboard() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchLeaderboard = async () => {
    try {
      const response = await axios.get(`${API_URL}/leaderboard`);
      setLeaderboard(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch leaderboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
  }, []);

  return { leaderboard, loading, error, refetch: fetchLeaderboard };
}
