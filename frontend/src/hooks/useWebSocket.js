// hooks/useWebSocket.js
import { useEffect, useRef, useState, useCallback } from 'react';

const MAX_RECONNECT_DELAY = 30000; // 30 seconds

export function useWebSocket(url) {
  const [prices, setPrices] = useState({});
  const [connected, setConnected] = useState(false);
  const ws = useRef(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    // Clean up existing connection
    if (ws.current) {
      ws.current.onclose = null;
      ws.current.close();
    }

    try {
      ws.current = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.current.onopen = () => {
      setConnected(true);
      reconnectAttempt.current = 0;
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // data = { ticker: "RELIANCE", price: 2847.30, change_pct: 0.84, ... }
        if (data.ticker) {
          setPrices(prev => ({ ...prev, [data.ticker]: data }));
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.current.onclose = () => {
      setConnected(false);
      scheduleReconnect();
    };

    ws.current.onerror = () => {
      setConnected(false);
    };
  }, [url]);

  const scheduleReconnect = useCallback(() => {
    // Exponential backoff: 3s → 6s → 12s → 24s → 30s (capped)
    const delay = Math.min(3000 * Math.pow(2, reconnectAttempt.current), MAX_RECONNECT_DELAY);
    reconnectAttempt.current += 1;

    reconnectTimer.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
    };
  }, [connect]);

  return { prices, connected };
}
