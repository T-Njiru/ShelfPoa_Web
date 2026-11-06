const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`Request to ${path} failed: ${res.status}`);
  return res.json();
}

// The live XGBoost endpoint returns one row per branch x SKU:
//   { chain, branch, sub_county, sku, predicted_units_next_week, rolling_mean_3w, lag_1w, forecast_week_start }
// The mock returns { branch_name, forecast_units_next_7d, ... }. Normalise both here so pages see one shape.
function normaliseForecast(r) {
  const predicted = Number(r.predicted_units_next_week ?? r.forecast_units_next_7d ?? 0);
  const recent = r.rolling_mean_3w != null ? Number(r.rolling_mean_3w) : null;
  const lastWeek = r.lag_1w != null ? Number(r.lag_1w) : null;
  return {
    sku: r.sku,
    branch_name: r.branch_name ?? [r.chain, r.branch].filter(Boolean).join(" "),
    sub_county: r.sub_county ?? "",
    forecast_units_next_7d: Math.round(predicted * 10) / 10,
    recent_avg: recent,
    // % change of next week's forecast vs the last 3 weeks' average (null when there is no history)
    trend_pct: recent ? Math.round((predicted / recent - 1) * 100) : null,
    // what the page shows: next week's forecast vs LAST WEEK's actual sales (null without history).
    // (A 3-week average is skewed by one-off spikes, e.g. a 79-unit week makes a normal week look like -26%.)
    last_week_units: lastWeek,
    change_pct: lastWeek ? Math.round((predicted / lastWeek - 1) * 100) : null,
    // % of last week the SKU was on the shelf (null when the backend has no shelf data)
    osa_last_week: r.osa_last_week_pct != null ? Math.round(Number(r.osa_last_week_pct)) : null,
  };
}

// Same call sites whether the backend is on mock or live data.
export const api = {
  getRecommendations: (limit = 10) => get(`/api/recommendations?limit=${limit}`),
  // Ask for everything, rank by predicted demand, then keep the top `limit` (null = all rows).
  getForecasts: async (limit = 10) => {
    const rows = (await get(`/api/forecast?limit=2000`))
      .map(normaliseForecast)
      .sort((a, b) => b.forecast_units_next_7d - a.forecast_units_next_7d);
    return limit == null ? rows : rows.slice(0, limit);
  },
  getMerchandiserSubmissions: (id, period = "latest") =>
    get(`/api/merchandisers/${encodeURIComponent(id)}/submissions?period=${period}`),
  getBasketRules: (limit = 10) => get(`/api/basket/rules?limit=${limit}`),
  getStockoutAlerts: (limit = 10) => get(`/api/stockouts?limit=${limit}`),
  getMerchandiserPerformance: (limit = 8) => get(`/api/merchandisers/performance?limit=${limit}`),
  getOutlets: () => get(`/api/outlets`),
  getShelfOpportunities: (limit = 3, kind) =>
    get(`/api/shelf/opportunities?limit=${limit}${kind ? `&kind=${kind}` : ""}`),
};

