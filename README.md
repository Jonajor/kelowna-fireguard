# KelownaFireGuard

**AI-Powered Wildfire Early Warning System for Kelowna, BC**

Real-time fire detection and alerting by cross-referencing satellite imagery, weather data, social media, news feeds, and official wildfire reports using NLP and multi-source AI analysis.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![React](https://img.shields.io/badge/react-18-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.115-green.svg)

---

## Overview

During wildfire events, critical information is scattered across radio, official reports, emergency messages, social media, and satellite imagery. KelownaFireGuard uses AI to aggregate and analyze all these sources in real-time, detecting early fire signals and generating alerts before official channels.

### Data Sources (All Free / Public APIs)

| Source | Data | Auth | Update Frequency |
|--------|------|------|-----------------|
| **BC Wildfire Service** | Active fires, perimeters, status | None (public ArcGIS) | 5 min |
| **NASA FIRMS** | Satellite fire hotspots (VIIRS/MODIS) | Free API key | 10 min |
| **Environment Canada** | Temperature, humidity, wind, FWI | None (OGC API) | 15 min |
| **Reddit** | Community fire reports | None (public JSON) | 2 min |
| **RSS News Feeds** | Castanet, CBC, Kelowna Now | None | 2 min |
| **OpenWeatherMap** | AQI, UV index, forecasts | Free tier (1000/day) | 15 min |

### Target Clients

- **City of Kelowna** — Emergency Operations Centre
- **BC Wildfire Service** — Regional fire monitoring
- **Regional District of Central Okanagan** — Public safety

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional) Docker & Docker Compose

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USER/kelowna-fireguard.git
cd kelowna-fireguard
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
NASA_FIRMS_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here  # optional
```

### 2a. Run with Docker (Recommended)

```bash
docker-compose up --build
```

### 2b. Run Manually

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/incidents` | Active fire incidents |
| `GET` | `/api/v1/alerts` | System-generated alerts |
| `GET` | `/api/v1/social` | AI-scored social media posts |
| `GET` | `/api/v1/weather` | Current weather + fire weather index |
| `GET` | `/api/v1/hotspots` | NASA satellite fire detections |
| `GET` | `/api/v1/analysis/risk` | Composite AI risk score |
| `GET` | `/api/v1/dashboard/stats` | Dashboard summary stats |
| `POST` | `/api/v1/analyze/text` | Run NLP on custom text |
| `WS` | `/api/v1/ws` | Real-time WebSocket updates |

---

## License

MIT
