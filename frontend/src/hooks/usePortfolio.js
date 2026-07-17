// hooks/usePortfolio.js
import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../config';

export function usePortfolio(authenticated) {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPortfolio = async () => {
    if (!authenticated) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API_URL}/portfolio`, {
        withCredentials: true,
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
  }, [authenticated]);

  return { portfolio, loading, error, refetch: fetchPortfolio };
}
