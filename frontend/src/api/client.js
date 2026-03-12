const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/api/v1/ws`;

async function fetchJSON(path, options = {}) {
  const url = `${API_BASE}${path}`;
  try {
    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (!resp.ok) throw new Error(`API ${resp.status}: ${resp.statusText}`);
    return await resp.json();
  } catch (err) {
    console.error(`[API] ${path} failed:`, err.message);
    return null;
  }
}

export async function getIncidents(params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`/incidents${q ? `?${q}` : ""}`);
}
export async function getIncident(id) { return fetchJSON(`/incidents/${id}`); }
export async function getAlerts(params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`/alerts${q ? `?${q}` : ""}`);
}
export async function acknowledgeAlert(id) { return fetchJSON(`/alerts/${id}/acknowledge`, { method: "PATCH" }); }
export async function getSocialFeed(params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`/social${q ? `?${q}` : ""}`);
}
export async function getWeather() { return fetchJSON("/weather"); }
export async function getWeatherHistory(hours = 24) { return fetchJSON(`/weather/history?hours=${hours}`); }
export async function getHotspots(params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJSON(`/hotspots${q ? `?${q}` : ""}`);
}
export async function getRiskAssessment() { return fetchJSON("/analysis/risk"); }
export async function analyzeText(text) {
  return fetchJSON("/analyze/text", { method: "POST", body: JSON.stringify({ text }) });
}
export async function getDashboardStats() { return fetchJSON("/dashboard/stats"); }
export async function getEvacuations() { return fetchJSON("/evacuations"); }

export function createWebSocket(onMessage, onError) {
  let ws = null, reconnectTimer = null, attempts = 0;
  function connect() {
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => { console.log("[WS] Connected"); attempts = 0; };
      ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch {} };
      ws.onerror = (err) => { if (onError) onError(err); };
      ws.onclose = () => { if (attempts < 10) { reconnectTimer = setTimeout(connect, 2000 * Math.pow(1.5, attempts++)); } };
    } catch { if (attempts < 10) { reconnectTimer = setTimeout(connect, 2000 * Math.pow(1.5, attempts++)); } }
  }
  connect();
  return { disconnect: () => { clearTimeout(reconnectTimer); if (ws) ws.close(); } };
}
