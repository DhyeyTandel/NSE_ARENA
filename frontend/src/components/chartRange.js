export const RANGES = ['1D', '1W', '1M', '1Y'];
export const INTRADAY = new Set(['1D', '1W']);
// lightweight-charts renders timestamps as UTC. Shift every bar by +5:30 so the
// axis/crosshair show IST wall-clock time for any viewer timezone. Daily bars
// are stamped at IST midnight (= previous day 18:30 UTC), so the same shift
// lands them on the correct IST calendar date.
export const IST_OFFSET_SECONDS = 19800;
