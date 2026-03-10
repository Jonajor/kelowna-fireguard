/**
 * KelownaFireGuard — Main Dashboard
 */
import { useState, useEffect, useCallback } from "react";
import { usePolledData } from "./hooks/usePolledData";
import {
  getIncidents,
  getAlerts,
  getSocialFeed,
  getWeather,
  getDashboardStats,
  getRiskAssessment,
  analyzeText,
  createWebSocket,
  getHotspots,
} from "./api/client";

const KELOWNA = { lat: 49.888, lng: -119.496 };
const THREAT_COLORS = {
  CRITICAL: "#FF2D2D",
  HIGH: "#FF8C00",
  MODERATE: "#FFD700",
  LOW: "#4ADE80",
};
const STATUS_COLORS = {
  active: "#FF4500",
  monitoring: "#FFD700",
  contained: "#4ADE80",
};
const PLATFORM_COLORS = {
  Reddit: "#FF5700",
  "Castanet Kelowna": "#E63946",
  "CBC British Columbia": "#D62828",
  "Global News Okanagan": "#1E88E5",
  InfoNews: "#7B2CBF",
  default: "#6B7280",
};

function ThreatBadge({ level }) {
  const color = THREAT_COLORS[level] || THREAT_COLORS.LOW;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3,
      background: `${color}18`, color, border: `1px solid ${color}33`,
      letterSpacing: 1, textTransform: "uppercase",
    }}>
      {level}
    </span>
  );
}

function ContainmentBar({ percent }) {
  const p = percent || 0;
  const color = p > 80 ? "#4ADE80" : p > 40 ? "#FFD700" : "#FF4500";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
      <div style={{ flex: 1, height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${p}%`, height: "100%", background: color, borderRadius: 2, transition: "width 1s ease" }} />
      </div>
      <span style={{ fontSize: 10, color: "#6B7280", minWidth: 30 }}>{p.toFixed(0)}%</span>
    </div>
  );
}

function LoadingDots() {
  return <div style={{ padding: 24, textAlign: "center", color: "#4B5563", fontSize: 11 }}>Loading data from collectors...</div>;
}

function EmptyState({ message }) {
  return <div style={{ padding: 24, textAlign: "center", color: "#4B5563", fontSize: 11 }}>{message}</div>;
}

function TabButton({ label, active, onClick, count }) {
  return (
    <button onClick={onClick} style={{
      background: active ? "rgba(255,69,0,0.12)" : "transparent",
      color: active ? "#FF8C00" : "#4B5563",
      border: `1px solid ${active ? "rgba(255,69,0,0.3)" : "transparent"}`,
      borderRadius: 4, padding: "4px 10px", fontSize: 9, fontWeight: 600,
      cursor: "pointer", letterSpacing: 0.5, fontFamily: "var(--font-mono)",
      display: "flex", alignItems: "center", gap: 4, transition: "all 0.2s",
    }}>
      {label}
      {count != null && (
        <span style={{
          background: active ? "#FF4500" : "rgba(255,255,255,0.06)",
          color: active ? "#fff" : "#6B7280",
          fontSize: 8, padding: "1px 4px", borderRadius: 3, fontWeight: 700,
        }}>{count}</span>
      )}
    </button>
  );
}

function IncidentCard({ incident, selected, onClick }) {
  const color = THREAT_COLORS[incident.threat_level] || "#6B7280";
  const statusColor = STATUS_COLORS[incident.status] || "#6B7280";
  const updated = incident.updated_at
    ? new Date(incident.updated_at).toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" })
    : "";
  return (
    <div onClick={onClick} style={{
      padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)",
      cursor: "pointer", background: selected ? "rgba(255,69,0,0.08)" : "transparent",
      borderLeft: `3px solid ${selected ? color : "transparent"}`,
      animation: "slideIn 0.3s ease", transition: "background 0.2s",
    }}
      onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
      onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = "transparent"; }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#E8EAED", flex: 1 }}>
          {incident.name}
        </span>
        <ThreatBadge level={incident.threat_level} />
      </div>
      <div style={{ display: "flex", gap: 12, fontSize: 10, color: "#6B7280", marginBottom: 4 }}>
        <span>{(incident.size_hectares || 0).toFixed(1)} ha</span>
        <span>•</span>
        <span style={{ color: statusColor }}>{(incident.status || "").toUpperCase()}</span>
        <span>•</span>
        <span>{updated}</span>
      </div>
      <ContainmentBar percent={incident.containment_pct || 0} />
      <div style={{ fontSize: 9, color: "#4B5563", marginTop: 4 }}>
        Source: {incident.source}{incident.fire_number && ` • ${incident.fire_number}`}
      </div>
    </div>
  );
}

function AlertCard({ alert }) {
  const color = THREAT_COLORS[alert.severity] || "#6B7280";
  const typeIcons = { evacuation_warning: "🚨", ai_detection: "🤖", weather_alert: "⛈️", social_media: "📡", sensor: "📟" };
  const time = alert.created_at
    ? new Date(alert.created_at).toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" })
    : "";
  return (
    <div style={{
      padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)",
      borderLeft: `3px solid ${color}`, animation: "slideIn 0.3s ease",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 14 }}>{typeIcons[alert.type] || "⚠️"}</span>
          <span style={{ fontSize: 11, fontWeight: 600, color }}>{alert.area}</span>
        </div>
        <span style={{ fontSize: 9, color: "#6B7280" }}>{time}</span>
      </div>
      <p style={{ fontSize: 11, color: "#9CA3AF", lineHeight: 1.5, margin: 0 }}>{alert.message}</p>
      {alert.source_count > 1 && (
        <div style={{ fontSize: 9, color: "#4B5563", marginTop: 4 }}>Corroborated by {alert.source_count} sources</div>
      )}
    </div>
  );
}

function SocialItem({ post }) {
  const scoreColor = post.ai_score > 0.9 ? "#FF4500" : post.ai_score > 0.8 ? "#FF8C00" : "#FFD700";
  const platColor = PLATFORM_COLORS[post.platform] || PLATFORM_COLORS.default;
  return (
    <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)", animation: "slideIn 0.3s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            fontSize: 8, fontWeight: 700, padding: "2px 5px", borderRadius: 3,
            background: `${platColor}22`, color: platColor, border: `1px solid ${platColor}44`,
            textTransform: "uppercase", letterSpacing: 0.5,
          }}>{post.platform}</span>
          <span style={{ fontSize: 10, color: "#6B7280" }}>{post.username}</span>
        </div>
        <span style={{ fontSize: 9, color: "#4B5563" }}>
          {post.collected_at ? new Date(post.collected_at).toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" }) : ""}
        </span>
      </div>
      <p style={{ fontSize: 11, color: "#D1D5DB", lineHeight: 1.5, margin: "0 0 8px 0" }}>
        {post.text?.slice(0, 250)}{post.text?.length > 250 ? "..." : ""}
      </p>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {(post.keywords || []).slice(0, 4).map((kw) => (
            <span key={kw} style={{
              fontSize: 8, padding: "1px 5px", borderRadius: 3,
              background: "rgba(255,255,255,0.04)", color: "#6B7280",
              border: "1px solid rgba(255,255,255,0.06)",
            }}>#{kw}</span>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 8, color: "#6B7280" }}>AI</span>
          <span style={{ fontSize: 11, fontWeight: 700, color: scoreColor }}>{((post.ai_score || 0) * 100).toFixed(0)}%</span>
        </div>
      </div>
      {post.location && <div style={{ fontSize: 9, color: "#4B5563", marginTop: 4 }}>📍 {post.location}</div>}
    </div>
  );
}

function WeatherPanel({ data }) {
  if (!data || !data.available) return <EmptyState message="Weather data loading... Collectors start within 15 min." />;
  const fwiColor = (data.fire_weather_index || 0) > 25 ? "#FF2D2D" : (data.fire_weather_index || 0) > 15 ? "#FF8C00" : "#FFD700";
  const StatBox = ({ label, value, unit, color }) => (
    <div style={{ textAlign: "center", padding: "12px 8px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.04)" }}>
      <div style={{ fontSize: 9, color: "#6B7280", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color || "#E8EAED", fontFamily: "var(--font-display)" }}>
        {value ?? "—"}{unit && <span style={{ fontSize: 10 }}>{unit}</span>}
      </div>
    </div>
  );
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
        <StatBox label="Temperature" value={data.temperature_c?.toFixed(1)} unit="°C" color="#FF4500" />
        <StatBox label="Humidity" value={data.humidity_pct?.toFixed(0)} unit="%" color="#FF8C00" />
        <StatBox label="Wind" value={data.wind_speed_kmh?.toFixed(0)} unit={` km/h ${data.wind_direction || ""}`} color="#FFD700" />
        <StatBox label="Fire Weather Index" value={data.fire_weather_index?.toFixed(1)} color={fwiColor} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
        <StatBox label="AQI" value={data.aqi} color={data.aqi > 150 ? "#FF4500" : "#FFD700"} />
        <StatBox label="UV" value={data.uv_index?.toFixed(1)} color="#FF8C00" />
        <StatBox label="VIS" value={data.visibility_km?.toFixed(1)} unit=" km" color="#FFD700" />
      </div>
      {data.fire_weather_rating && (
        <div style={{ padding: "8px 12px", borderRadius: 6, background: "rgba(255,69,0,0.06)", border: "1px solid rgba(255,69,0,0.15)", fontSize: 10, color: "#FF8C00", lineHeight: 1.5 }}>
          Fire Weather: <strong>{data.fire_weather_rating}</strong>{data.condition && ` • ${data.condition}`}
        </div>
      )}
      <div style={{ fontSize: 9, color: "#4B5563", marginTop: 8 }}>
        Source: {data.source || "Environment Canada"} • Updated: {data.recorded_at ? new Date(data.recorded_at).toLocaleTimeString("en-CA") : "—"}
      </div>
    </div>
  );
}

function AIPanel({ riskData }) {
  const [textInput, setTextInput] = useState("");
  const [textResult, setTextResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  const handleAnalyze = async () => {
    if (!textInput.trim()) return;
    setAnalyzing(true);
    const result = await analyzeText(textInput);
    setTextResult(result);
    setAnalyzing(false);
  };

  const risk = riskData;
  const riskColor = !risk ? "#6B7280" : risk.risk_score >= 85 ? "#FF2D2D" : risk.risk_score >= 60 ? "#FF8C00" : risk.risk_score >= 30 ? "#FFD700" : "#4ADE80";

  return (
    <div style={{ padding: 16 }}>
      <div style={{ textAlign: "center", padding: 16, marginBottom: 12, background: risk ? `${riskColor}12` : "rgba(255,255,255,0.02)", border: `1px solid ${riskColor}33`, borderRadius: 8 }}>
        <div style={{ fontSize: 8, color: "#6B7280", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 4 }}>AI Risk Score</div>
        <div style={{ fontSize: 42, fontWeight: 800, color: riskColor, fontFamily: "var(--font-display)" }}>{risk ? risk.risk_score : "—"}</div>
        <div style={{ fontSize: 10, color: riskColor, fontWeight: 600 }}>{risk?.rating || "Waiting for data..."}</div>
      </div>
      {risk?.components && (
        <div style={{ marginBottom: 12 }}>
          {Object.entries(risk.components).map(([key, val]) => {
            const score = typeof val === "object" ? val.score : val;
            const count = typeof val === "object" ? val.count : null;
            return (
              <div key={key} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.03)", fontSize: 10 }}>
                <span style={{ color: "#9CA3AF", textTransform: "capitalize" }}>
                  {key.replace(/_/g, " ")}{count != null && <span style={{ color: "#4B5563" }}> ({count})</span>}
                </span>
                <span style={{ color: score > 15 ? "#FF4500" : score > 5 ? "#FFD700" : "#4ADE80", fontWeight: 600 }}>{score}/25</span>
              </div>
            );
          })}
        </div>
      )}
      <div style={{ marginTop: 16, borderTop: "1px solid rgba(255,255,255,0.04)", paddingTop: 12 }}>
        <div style={{ fontSize: 9, color: "#6B7280", letterSpacing: 1.5, marginBottom: 8, textTransform: "uppercase" }}>Test NLP Engine</div>
        <textarea value={textInput} onChange={(e) => setTextInput(e.target.value)}
          placeholder="Paste text to analyze for fire signals..."
          style={{ width: "100%", height: 60, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, color: "#E8EAED", padding: 8, fontSize: 11, fontFamily: "var(--font-mono)", resize: "vertical" }}
        />
        <button onClick={handleAnalyze} disabled={analyzing} style={{
          width: "100%", marginTop: 6, padding: "8px 12px",
          background: analyzing ? "rgba(255,69,0,0.1)" : "linear-gradient(135deg, #FF4500, #FF8C00)",
          color: analyzing ? "#FF8C00" : "#000", border: "none", borderRadius: 6,
          fontSize: 10, fontWeight: 700, cursor: analyzing ? "wait" : "pointer", fontFamily: "var(--font-mono)",
        }}>
          {analyzing ? "ANALYZING..." : "ANALYZE TEXT"}
        </button>
        {textResult && (
          <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)", borderRadius: 6, fontSize: 10, animation: "slideIn 0.3s ease" }}>
            <div style={{ color: textResult.is_fire_related ? "#FF4500" : "#4ADE80", fontWeight: 700, marginBottom: 4 }}>
              Score: {((textResult.fire_score || 0) * 100).toFixed(0)}% — {textResult.is_fire_related ? "FIRE RELATED" : "Not fire related"}
            </div>
            <div style={{ color: "#9CA3AF" }}>Keywords: {(textResult.keywords || []).join(", ") || "none"}</div>
            <div style={{ color: "#6B7280" }}>Sentiment: {textResult.sentiment} | Location: {textResult.extracted_location || "—"}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function MapView({ incidents, hotspots, selected, onSelect }) {
  const bounds = { minLat: 49.60, maxLat: 50.15, minLng: -119.90, maxLng: -119.10 };
  const toXY = (lat, lng) => ({
    x: ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * 100,
    y: ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * 100,
  });
  const allIncidents = incidents || [];
  const allHotspots = hotspots || [];

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", background: "#080A0E" }}>
      <svg width="100%" height="100%" style={{ position: "absolute", opacity: 0.06 }}>
        {Array.from({ length: 20 }).map((_, i) => (
          <line key={`h${i}`} x1="0" y1={`${i * 5}%`} x2="100%" y2={`${i * 5}%`} stroke="#fff" strokeWidth="0.5" />
        ))}
        {Array.from({ length: 20 }).map((_, i) => (
          <line key={`v${i}`} x1={`${i * 5}%`} y1="0" x2={`${i * 5}%`} y2="100%" stroke="#fff" strokeWidth="0.5" />
        ))}
      </svg>
      <svg width="100%" height="100%" style={{ position: "absolute", opacity: 0.08 }}>
        <path d="M 35,10 Q 33,25 32,40 Q 31,50 30,60 Q 29,70 28,80 Q 27,87 26,95" fill="none" stroke="#1E90FF" strokeWidth="12" strokeLinecap="round" opacity="0.5" />
        <text x="28%" y="50%" fill="#1E90FF" fontSize="9" opacity="0.6" fontFamily="var(--font-mono)">Okanagan Lake</text>
      </svg>
      <div style={{ position: "absolute", left: "42%", top: "38%", color: "rgba(255,255,255,0.12)", fontSize: 28, fontWeight: 800, letterSpacing: 6, textTransform: "uppercase", fontFamily: "var(--font-display)", pointerEvents: "none" }}>
        KELOWNA
      </div>
      {allHotspots.map((h, i) => {
        const pos = toXY(h.latitude, h.longitude);
        return (
          <div key={`hs-${i}`} style={{ position: "absolute", left: `${pos.x}%`, top: `${pos.y}%`, width: 6, height: 6, borderRadius: "50%", background: "rgba(255,165,0,0.6)", border: "1px solid rgba(255,165,0,0.3)", transform: "translate(-50%, -50%)", pointerEvents: "none" }} />
        );
      })}
      {allIncidents.map((inc) => {
        const pos = toXY(inc.latitude, inc.longitude);
        const color = THREAT_COLORS[inc.threat_level] || "#6B7280";
        const isSel = selected?.id === inc.id;
        const isActive = inc.status === "active";
        return (
          <div key={inc.id} onClick={() => onSelect(isSel ? null : inc)} style={{ position: "absolute", left: `${pos.x}%`, top: `${pos.y}%`, transform: "translate(-50%, -50%)", cursor: "pointer", zIndex: isSel ? 50 : 10 }}>
            {isActive && (
              <>
                <div style={{ position: "absolute", left: "50%", top: "50%", width: 40, height: 40, borderRadius: "50%", border: `2px solid ${color}`, transform: "translate(-50%, -50%)", animation: "pulseRing 2s infinite", opacity: 0.4 }} />
                <div style={{ position: "absolute", left: "50%", top: "50%", width: 40, height: 40, borderRadius: "50%", border: `2px solid ${color}`, transform: "translate(-50%, -50%)", animation: "pulseRing 2s infinite 0.6s", opacity: 0.3 }} />
              </>
            )}
            <div style={{ width: isSel ? 18 : 14, height: isSel ? 18 : 14, borderRadius: "50%", background: `radial-gradient(circle, ${color}, ${color}88)`, border: `2px solid ${isSel ? "#fff" : color}`, boxShadow: `0 0 ${isSel ? 20 : 12}px ${color}66`, transition: "all 0.3s" }} />
            {isSel && (
              <div style={{ position: "absolute", top: "-44px", left: "50%", transform: "translateX(-50%)", background: "rgba(13,15,20,0.95)", border: `1px solid ${color}44`, borderRadius: 6, padding: "6px 10px", whiteSpace: "nowrap", animation: "slideIn 0.2s ease" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color }}>{inc.name}</div>
                <div style={{ fontSize: 8, color: "#6B7280" }}>{(inc.size_hectares || 0).toFixed(1)} ha • {(inc.containment_pct || 0).toFixed(0)}% contained</div>
              </div>
            )}
          </div>
        );
      })}
      <div style={{ position: "absolute", bottom: 16, left: 16, background: "rgba(13,15,20,0.9)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8, padding: "10px 14px", backdropFilter: "blur(8px)" }}>
        <div style={{ fontSize: 8, fontWeight: 700, color: "#6B7280", letterSpacing: 1.5, marginBottom: 8, textTransform: "uppercase" }}>Threat Level</div>
        {Object.entries(THREAT_COLORS).map(([key, color]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
            <span style={{ fontSize: 9, color: "#9CA3AF" }}>{key}</span>
          </div>
        ))}
        {allHotspots.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4, paddingTop: 4, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "rgba(255,165,0,0.6)" }} />
            <span style={{ fontSize: 9, color: "#9CA3AF" }}>Satellite hotspot</span>
          </div>
        )}
      </div>
      <div style={{ position: "absolute", bottom: 16, right: 16, background: "rgba(13,15,20,0.9)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, padding: "6px 10px", fontSize: 9, color: "#4B5563" }}>
        {KELOWNA.lat.toFixed(4)}°N, {Math.abs(KELOWNA.lng).toFixed(4)}°W • {allIncidents.length} incidents • {allHotspots.length} hotspots
      </div>
      <div style={{ position: "absolute", left: 0, width: "100%", height: "2px", background: "linear-gradient(90deg, transparent, rgba(255,69,0,0.08), transparent)", animation: "scanline 8s linear infinite", pointerEvents: "none" }} />
    </div>
  );
}

export default function App() {
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [leftTab, setLeftTab] = useState("alerts");
  const [rightTab, setRightTab] = useState("social");
  const [time, setTime] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);

  const { data: statsData } = usePolledData(getDashboardStats, 15000);
  const { data: incidentsData, loading: incLoading } = usePolledData(getIncidents, 30000);
  const { data: alertsData, loading: alertLoading } = usePolledData(
    useCallback(() => getAlerts({ hours: 24 }), []), 20000
  );
  const { data: socialData, loading: socLoading } = usePolledData(
    useCallback(() => getSocialFeed({ min_score: 0.5, hours: 12 }), []), 30000
  );
  const { data: weatherData } = usePolledData(getWeather, 60000);
  const { data: riskData } = usePolledData(getRiskAssessment, 30000);
  const { data: hotspotsData } = usePolledData(
    useCallback(() => getHotspots({ hours: 48 }), []), 60000
  );

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const ws = createWebSocket(
      (msg) => { setWsConnected(true); },
      () => setWsConnected(false)
    );
    return () => ws.disconnect();
  }, []);

  const incidents = incidentsData?.incidents || [];
  const alerts = alertsData?.alerts || [];
  const socialPosts = socialData?.posts || [];
  const hotspots = hotspotsData?.hotspots || [];
  const stats = statsData || {};

  return (
    <div style={{ background: "var(--bg-primary)", color: "var(--text-primary)", fontFamily: "var(--font-mono)", minHeight: "100vh" }}>
      <header style={{
        background: "linear-gradient(180deg, var(--bg-tertiary) 0%, var(--bg-primary) 100%)",
        borderBottom: "1px solid rgba(255,69,0,0.2)", padding: "12px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        position: "sticky", top: 0, zIndex: 100, backdropFilter: "blur(12px)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 20 }}>🔥</span>
          <span style={{ fontSize: 22, fontWeight: 800, background: "linear-gradient(135deg, #FF4500, #FF8C00, #FFD700)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", letterSpacing: "-0.5px", fontFamily: "var(--font-display)" }}>
            KELOWNA FIREGUARD
          </span>
          <span style={{ fontSize: 9, background: "rgba(255,69,0,0.15)", color: "#FF8C00", padding: "2px 8px", borderRadius: 4, border: "1px solid rgba(255,69,0,0.3)", textTransform: "uppercase", letterSpacing: 1.5, fontWeight: 700 }}>
            AI-Powered
          </span>
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "center", fontSize: 11, color: "#8B8F96" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: wsConnected ? "#4ADE80" : "#FF4500", animation: "pulse 2s infinite", display: "inline-block" }} />
            <span style={{ color: wsConnected ? "#4ADE80" : "#FF4500", fontWeight: 600 }}>{wsConnected ? "LIVE" : "CONNECTING"}</span>
          </div>
          <span>|</span>
          <span>{time.toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" })}</span>
          <span>{time.toLocaleTimeString("en-CA", { hour12: false })}</span>
          <span>|</span>
          <span>Kelowna, BC</span>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 1, background: "rgba(255,255,255,0.03)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
        {[
          { label: "Active", value: stats.active_fires ?? "—", color: "#FF2D2D" },
          { label: "Monitoring", value: stats.monitoring ?? "—", color: "#FFD700" },
          { label: "Contained", value: stats.contained ?? "—", color: "#4ADE80" },
          { label: "Total Area", value: stats.total_area_ha != null ? `${stats.total_area_ha} ha` : "—", color: "#FF8C00" },
          { label: "Unack. Alerts", value: stats.unacknowledged_alerts ?? "—", color: "#FF2D2D" },
        ].map((s) => (
          <div key={s.label} style={{ padding: "12px 16px", background: "var(--bg-secondary)", textAlign: "center" }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: s.color, fontFamily: "var(--font-display)" }}>{s.value}</div>
            <div style={{ fontSize: 8, color: "#6B7280", textTransform: "uppercase", letterSpacing: 1.5, fontWeight: 600 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr 340px", gap: 1, height: "calc(100vh - 106px)", background: "rgba(255,255,255,0.03)" }}>
        <div style={{ background: "var(--bg-secondary)", overflow: "auto" }}>
          <div style={{ padding: "14px 16px 10px", display: "flex", gap: 4, borderBottom: "1px solid var(--border)", position: "sticky", top: 0, background: "var(--bg-secondary)", zIndex: 10 }}>
            <TabButton label="ALERTS" active={leftTab === "alerts"} onClick={() => setLeftTab("alerts")} count={alerts.length} />
            <TabButton label="INCIDENTS" active={leftTab === "incidents"} onClick={() => setLeftTab("incidents")} count={incidents.length} />
          </div>
          {leftTab === "incidents"
            ? incLoading ? <LoadingDots />
              : incidents.length === 0 ? <EmptyState message="No active incidents detected in the Kelowna region." />
              : incidents.map((inc) => <IncidentCard key={inc.id} incident={inc} selected={selectedIncident?.id === inc.id} onClick={() => setSelectedIncident(selectedIncident?.id === inc.id ? null : inc)} />)
            : alertLoading ? <LoadingDots />
              : alerts.length === 0 ? <EmptyState message="No alerts in the last 24 hours. System is monitoring." />
              : alerts.map((a) => <AlertCard key={a.id} alert={a} />)
          }
        </div>

        <div style={{ background: "#080A0E", position: "relative", overflow: "hidden" }}>
          <MapView incidents={incidents} hotspots={hotspots} selected={selectedIncident} onSelect={setSelectedIncident} />
        </div>

        <div style={{ background: "var(--bg-secondary)", overflow: "auto", borderLeft: "1px solid var(--border)" }}>
          <div style={{ padding: "14px 16px 10px", display: "flex", gap: 4, borderBottom: "1px solid var(--border)", position: "sticky", top: 0, background: "var(--bg-secondary)", zIndex: 10 }}>
            <TabButton label="SOCIAL" active={rightTab === "social"} onClick={() => setRightTab("social")} count={socialPosts.length} />
            <TabButton label="WEATHER" active={rightTab === "weather"} onClick={() => setRightTab("weather")} />
            <TabButton label="AI" active={rightTab === "ai"} onClick={() => setRightTab("ai")} />
          </div>
          {rightTab === "social"
            ? <>
                <div style={{ padding: "8px 16px", background: "rgba(255,69,0,0.04)", borderBottom: "1px solid var(--border)", fontSize: 9, color: "#FF8C00", display: "flex", alignItems: "center", gap: 6 }}>
                  📡 NLP scanning Reddit, news RSS, and social feeds in real-time
                </div>
                {socLoading ? <LoadingDots />
                  : socialPosts.length === 0 ? <EmptyState message="No fire-related posts detected. Scanner runs every 2 minutes." />
                  : socialPosts.map((p) => <SocialItem key={p.id} post={p} />)
                }
              </>
            : rightTab === "weather"
            ? <WeatherPanel data={weatherData} />
            : <AIPanel riskData={riskData} />
          }
        </div>
      </div>
    </div>
  );
}
