// hooks/usePortfolio.js
import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

export function usePortfolio(token) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPortfolio = async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API_URL}/portfolio`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPortfolio(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch portfolio');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();
  }, [token]);

  return { portfolio, loading, error, refetch: fetchPortfolio };
}
