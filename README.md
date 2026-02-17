# Intelligent Log Analyzer & Incident Assistant

A full-stack intelligent log analysis platform that ingests log files, parses and normalizes entries, detects anomalies using machine learning (Isolation Forest), clusters similar errors, and presents everything through an interactive dark-themed dashboard with rich Chart.js visualizations.

## Features

### Backend (FastAPI + Python)

- **Log Ingestion Pipeline** — Upload log files (syslog, JSON, custom formats) via REST API; automatic parsing and normalization into structured entries with timestamp, level, service, and message fields
- **Multi-Format Parser** — Extensible parser system supporting syslog, JSON, and common log formats with confidence scoring and fallback handling
- **Anomaly Detection (Isolation Forest)** — ML-based anomaly detection that analyzes 2-minute time windows, computing features like error rate, event count, warning count, and unique service count to identify unusual log patterns
- **Error Clustering (TF-IDF + K-Means)** — Groups similar error messages into clusters using TF-IDF vectorization and K-Means clustering, extracting top keywords and tracking first/last seen timestamps
- **JWT + API Key Authentication** — Secure auth system with role-based access control (Admin / Viewer), JWT token authentication, and revocable API keys
- **Statistics Engine** — Real-time aggregation of log level breakdowns, top services, file processing status, and entry counts
- **Structured Logging** — JSON-formatted application logs with request timing middleware

### Frontend (Vanilla JS SPA)

- **Dark-Themed Dashboard** — Cyberpunk-inspired UI with violet accent colors, animated sidebar with circuit-node decorations, and glassmorphic effects
- **10 Interactive Charts** (Chart.js) — Organized into stats-based charts (always visible) and analytics-based charts (populated after running ML pipeline):
  - **Log Level Breakdown** — Doughnut chart with center total count
  - **Top Services** — Horizontal bar chart of most active services
  - **Log Volume Timeline** — Line chart showing event volume over time with error/warning overlays
  - **Severity Radar** — Radar chart showing log level distribution shape
  - **Anomaly Score Timeline** — Color-coded line chart (green/yellow/red) with gradient fill
  - **Error Rate & Event Volume** — Dual-axis chart correlating error rate with event volume
  - **Log Composition Over Time** — Stacked area chart of ERROR/WARNING/INFO/DEBUG per window
  - **Anomaly Score Distribution** — Histogram showing score ranges (normal/moderate/high)
  - **Top Error Clusters** — Horizontal bar chart with tooltips showing example messages
  - **Service Activity Over Time** — Unique services + warning count dual-axis chart
- **Run Analytics Button** — One-click ML pipeline trigger with auto-polling and dashboard refresh
- **Log Explorer** — Paginated, filterable log entry browser with level/service/keyword/date filters
- **File Manager** — Upload interface with drag-and-drop and processing status tracking
- **Anomalies Page** — Tabular view of all detected anomalies with score bars
- **Error Clusters Page** — Card-based view of error clusters with keywords and example messages
- **Settings Page** — Profile info, API key management, and user creation (admin)
- **SPA Router** — Hash-based routing with auth guards and sidebar navigation

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL (via Docker) |
| ML | scikit-learn (Isolation Forest, TF-IDF, K-Means) |
| Auth | python-jose (JWT), passlib + bcrypt |
| Frontend | Vanilla JavaScript (ES6 modules), Chart.js 4 |
| Styling | Custom CSS with CSS variables, animations, responsive grid |
| Dev Tools | pytest, httpx, uvicorn |

## Project Structure

```
.
├── app/
│   ├── core/               # Config, logging, auth dependencies
│   │   ├── config.py
│   │   ├── logging_config.py
│   │   └── dependencies.py
│   ├── db/                 # Database session and engine
│   │   └── session.py
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── log_entry.py
│   │   ├── log_file.py
│   │   ├── anomaly.py
│   │   ├── error_cluster.py
│   │   ├── pipeline_run.py
│   │   └── user.py
│   ├── routes/             # FastAPI route handlers
│   │   ├── auth.py         # Login, user/key management
│   │   ├── logs.py         # File upload, log entry queries
│   │   ├── stats.py        # Summary statistics
│   │   └── analytics.py    # Anomalies, clusters, pipeline trigger
│   ├── schemas/            # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── analytics.py
│   │   ├── log_entry.py
│   │   ├── log_file.py
│   │   ├── stats.py
│   │   └── pagination.py
│   ├── services/           # Business logic
│   │   ├── parsers.py      # Log parsing engine
│   │   ├── ingestion.py    # File processing pipeline
│   │   └── analytics.py    # ML anomaly detection & clustering
│   └── main.py             # FastAPI app entry point
├── static/
│   ├── css/style.css       # Full dark theme stylesheet
│   ├── index.html          # SPA shell
│   └── js/
│       ├── api.js          # HTTP client with auth headers
│       ├── app.js          # SPA router and app initialization
│       └── pages/
│           ├── dashboard.js    # Dashboard with 10 Chart.js charts
│           ├── login.js        # Login form
│           ├── logs.js         # Log explorer with filters
│           ├── files.js        # File upload and management
│           ├── anomalies.js    # Anomaly detection results table
│           ├── clusters.js     # Error cluster cards
│           └── settings.js     # User settings, API keys, admin tools
├── alembic/                # Database migrations
├── tests/                  # pytest test suite
├── docs/                   # Design documents
├── docker-compose.yml      # PostgreSQL container
├── requirements.txt        # Python dependencies
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for PostgreSQL)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/muhit009/Intelligent-log-analyzer-Incident-Assistant.git
   cd Intelligent-log-analyzer-Incident-Assistant
   ```

2. **Start PostgreSQL**
   ```bash
   docker-compose up -d
   ```

3. **Create virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

4. **Configure environment** — Copy `.env.example` to `.env` and update values:
   ```
   DATABASE_URL=postgresql://...
   JWT_SECRET_KEY=your-secret-key
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Open the app** — Navigate to `http://localhost:8000`

### First-Time Usage

1. Create an admin user (via API or seed script)
2. Login at the dashboard
3. Upload log files via the **Files** page
4. Click **Run Analytics** on the Dashboard to trigger the ML pipeline
5. All 10 charts populate with anomaly detection and clustering results

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/login` | Public | Get JWT token |
| `GET` | `/auth/me` | Any | Current user profile |
| `POST` | `/auth/users` | Admin | Create new user |
| `POST` | `/auth/api-keys` | Any | Create API key |
| `GET` | `/auth/api-keys` | Any | List API keys |
| `DELETE` | `/auth/api-keys/{id}` | Any | Revoke API key |
| `POST` | `/logs/upload` | Admin | Upload log file |
| `GET` | `/logs/files` | Viewer+ | List uploaded files |
| `GET` | `/logs` | Viewer+ | Query log entries (filterable) |
| `GET` | `/stats/summary` | Viewer+ | Dashboard statistics |
| `GET` | `/analytics/anomalies` | Viewer+ | List detected anomalies |
| `GET` | `/analytics/clusters` | Viewer+ | List error clusters |
| `POST` | `/analytics/run` | Admin | Trigger ML analytics pipeline |
| `GET` | `/health` | Public | Health check |
| `GET` | `/docs` | Public | Swagger UI (auto-generated) |

## ML Pipeline Details

### Anomaly Detection

- Segments log entries into **2-minute time windows**
- Computes per-window features: `total_count`, `error_count`, `warn_count`, `info_count`, `debug_count`, `error_rate`, `unique_services`
- Applies **Isolation Forest** (10% contamination) to identify anomalous windows
- Scores normalized to 0-1 range (higher = more anomalous)

### Error Clustering

- Filters ERROR-level log messages
- Applies **TF-IDF vectorization** on message text
- Groups into up to **20 clusters** using **K-Means**
- Extracts top 5 keywords per cluster
- Tracks temporal span (`first_seen` / `last_seen`)

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT
