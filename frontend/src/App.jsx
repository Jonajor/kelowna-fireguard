/**
 * KelownaFireGuard — Main Dashboard
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, useMapEvents } from "react-leaflet";
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
  getEvacuations,
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
const EVAC_COLORS = {
  "Order": "#FF2D2D",
  "Alert": "#FF8C00",
  "Tactical Evacuation": "#FFD700",
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

function FlyToSelected({ selected }) {
  const map = useMap();
  useEffect(() => {
    if (selected?.latitude && selected?.longitude) {
      map.flyTo([selected.latitude, selected.longitude], 13, { duration: 1 });
    }
  }, [selected, map]);
  return null;
}

function LocationMarker({ position }) {
  if (!position) return null;
  return (
    <CircleMarker
      center={position}
      radius={8}
      pathOptions={{ color: "#4ADE80", fillColor: "#4ADE80", fillOpacity: 0.9, weight: 3 }}
    >
      <Popup>
        <div style={{ fontFamily: "monospace", fontSize: 11 }}>
          <strong style={{ color: "#4ADE80" }}>Your Location</strong><br />
          {position[0].toFixed(5)}°N, {Math.abs(position[1]).toFixed(5)}°W
        </div>
      </Popup>
    </CircleMarker>
  );
}

function MapView({ incidents, hotspots, evacuations, selected, onSelect, userLocation }) {
  const allIncidents = incidents || [];
  const allHotspots = hotspots || [];
  const allEvacuations = (evacuations || []).filter(e => e.latitude && e.longitude);

  return (
    <MapContainer
      center={[KELOWNA.lat, KELOWNA.lng]}
      zoom={10}
      style={{ width: "100%", height: "100%" }}
      zoomControl={true}
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        maxZoom={19}
        className="map-tiles-dark"
      />
      <FlyToSelected selected={selected} />

      {allHotspots.map((h, i) => (
        <CircleMarker
          key={`hs-${i}`}
          center={[h.latitude, h.longitude]}
          radius={5}
          pathOptions={{ color: "#FFA500", fillColor: "#FFA500", fillOpacity: 0.6, weight: 1 }}
        >
          <Popup>
            <div style={{ fontFamily: "monospace", fontSize: 11 }}>
              <strong style={{ color: "#FFA500" }}>Satellite Hotspot</strong><br />
              Brightness: {h.brightness?.toFixed(1)} K<br />
              Confidence: {h.confidence}<br />
              FRP: {h.frp?.toFixed(1)} MW<br />
              {h.acq_date} {h.acq_time}
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {allEvacuations.map((evac) => {
        const color = EVAC_COLORS[evac.status] || "#FFD700";
        return (
          <CircleMarker
            key={evac.id}
            center={[evac.latitude, evac.longitude]}
            radius={14}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.25, weight: 2.5, dashArray: "6 4" }}
          >
            <Popup>
              <div style={{ fontFamily: "monospace", fontSize: 11, minWidth: 180 }}>
                <strong style={{ color }}>{evac.status?.toUpperCase()}</strong>
                {" — "}{evac.event_name}<br />
                Type: {evac.event_type}<br />
                Agency: {evac.issuing_agency}<br />
                {evac.homes_affected != null && <>Homes: {evac.homes_affected}<br /></>}
                {evac.population_affected != null && <>People: {evac.population_affected}<br /></>}
                {evac.event_start_date && <>Since: {new Date(evac.event_start_date).toLocaleDateString()}</>}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      {allIncidents.map((inc) => {
        const color = THREAT_COLORS[inc.threat_level] || "#6B7280";
        const isSel = selected?.id === inc.id;
        const radius = isSel ? 12 : inc.status === "active" ? 10 : 7;
        return (
          <CircleMarker
            key={inc.id}
            center={[inc.latitude, inc.longitude]}
            radius={radius}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: isSel ? 0.9 : 0.7,
              weight: isSel ? 3 : 1.5,
            }}
            eventHandlers={{ click: () => onSelect(isSel ? null : inc) }}
          >
            <Popup>
              <div style={{ fontFamily: "monospace", fontSize: 11, minWidth: 160 }}>
                <strong style={{ color }}>{inc.name}</strong><br />
                <span style={{ color: STATUS_COLORS[inc.status] || "#fff" }}>{(inc.status || "").toUpperCase()}</span>
                {" • "}<ThreatBadge level={inc.threat_level} /><br />
                Size: {(inc.size_hectares || 0).toFixed(2)} ha<br />
                Containment: {(inc.containment_pct || 0).toFixed(0)}%<br />
                {inc.fire_number && <>ID: {inc.fire_number}<br /></>}
                {inc.fire_cause && <>Cause: {inc.fire_cause}<br /></>}
                Source: {inc.source}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
      <LocationMarker position={userLocation} />
    </MapContainer>
  );
}

export default function App() {
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [leftTab, setLeftTab] = useState("alerts");
  const [rightTab, setRightTab] = useState("social");
  const [time, setTime] = useState(new Date());
  const [wsConnected, setWsConnected] = useState(false);
  const [userLocation, setUserLocation] = useState(null);

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
  const { data: evacuationsData } = usePolledData(getEvacuations, 60000);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (pos) => setUserLocation([pos.coords.latitude, pos.coords.longitude]),
      () => {},
      { enableHighAccuracy: true }
    );
    return () => navigator.geolocation.clearWatch(id);
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
  const evacuations = evacuationsData?.evacuations || [];
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
            <TabButton label="EVAC" active={leftTab === "evac"} onClick={() => setLeftTab("evac")} count={evacuations.length} />
            <TabButton label="INCIDENTS" active={leftTab === "incidents"} onClick={() => setLeftTab("incidents")} count={incidents.length} />
          </div>
          {leftTab === "incidents"
            ? incLoading ? <LoadingDots />
              : incidents.length === 0 ? <EmptyState message="No active incidents detected in the Kelowna region." />
              : incidents.map((inc) => <IncidentCard key={inc.id} incident={inc} selected={selectedIncident?.id === inc.id} onClick={() => setSelectedIncident(selectedIncident?.id === inc.id ? null : inc)} />)
            : leftTab === "evac"
            ? evacuations.length === 0
              ? <EmptyState message="No active evacuation orders or alerts in the region." />
              : evacuations.map((evac) => {
                  const color = EVAC_COLORS[evac.status] || "#FFD700";
                  return (
                    <div key={evac.id} style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.03)", borderLeft: `3px solid ${color}` }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color }}>{evac.status?.toUpperCase()}</span>
                        <span style={{ fontSize: 9, color: "#6B7280" }}>{evac.event_type}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#E8EAED", marginBottom: 4 }}>{evac.event_name}</div>
                      <div style={{ fontSize: 10, color: "#9CA3AF" }}>{evac.issuing_agency}</div>
                      {(evac.homes_affected || evac.population_affected) && (
                        <div style={{ fontSize: 9, color: "#6B7280", marginTop: 4 }}>
                          {evac.homes_affected != null && `${evac.homes_affected} homes`}
                          {evac.homes_affected && evac.population_affected ? " • " : ""}
                          {evac.population_affected != null && `${evac.population_affected} people`}
                        </div>
                      )}
                    </div>
                  );
                })
            : alertLoading ? <LoadingDots />
              : alerts.length === 0 ? <EmptyState message="No alerts in the last 24 hours. System is monitoring." />
              : alerts.map((a) => <AlertCard key={a.id} alert={a} />)
          }
        </div>

        <div style={{ background: "#080A0E", position: "relative", overflow: "hidden" }}>
          <MapView incidents={incidents} hotspots={hotspots} evacuations={evacuations} selected={selectedIncident} onSelect={setSelectedIncident} userLocation={userLocation} />
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
