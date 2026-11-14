// hooks/useSeasonStanding.js
// Real season + leaderboard + score data, shared by Dashboard, Leaderboard
// and Profile. Anything that cannot be derived is null, never invented.
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { API_URL } from '../config';

export function useSeasonStanding(authenticated, user) {
  const [season, setSeason] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [score, setScore] = useState(null);
  const [loading, setLoading] = useState(true);
  const userId = user?.id;

  useEffect(() => {
    let cancelled = false;
    const get = async (path, opts) => {
      try {
        const r = await axios.get(`${API_URL}${path}`, opts);
        return r.data;
      } catch {
        return null;
      }
    };
    const load = async () => {
      const [s, lb, sc] = await Promise.all([
        get('/seasons/active'),
        get('/leaderboard'),
        authenticated && userId != null ? get(`/score/${userId}`) : Promise.resolve(null),
      ]);
      if (cancelled) return;
      setSeason(s && s.id != null ? s : null);
      setLeaderboard(Array.isArray(lb) ? lb : []);
      setScore(sc && sc.final_score != null ? sc : null);
      setLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, [authenticated, userId]);

  const standing = useMemo(() => {
    const sorted = [...leaderboard].sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9));
    const idx = userId == null ? -1 : sorted.findIndex(e => e.user_id === userId);
    const me = idx >= 0 ? sorted[idx] : null;
    const ahead = idx > 0 ? sorted[idx - 1] : null;
    return {
      me,
      rank: me ? (me.rank ?? idx + 1) : null,
      traderCount: sorted.length,
      aheadRank: ahead ? (ahead.rank ?? idx) : null,
      gapToNext: me && ahead ? Math.max(0, ahead.total_value - me.total_value) : null,
    };
  }, [leaderboard, userId]);

  const daysLeft = season?.end_date
    ? Math.max(0, Math.ceil((new Date(season.end_date) - new Date()) / 86400000))
    : null;

  return { season, daysLeft, leaderboard, score, loading, ...standing };
}
