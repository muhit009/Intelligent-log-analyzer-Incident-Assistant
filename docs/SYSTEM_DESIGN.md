#C4 Container Diagram - Intelligent Log Analyzer
```mermaid
flowchart TB

%% People
subgraph People
  U[Person: User or Admin]
end

%% Sources
subgraph Sources["Log Sources"]
  S1[External: Nginx access logs]
  S2[External: App logs]
  S3[External: Other log or txt sources]
end

%% System boundary
subgraph SYS["System: Intelligent Log Analyzer and Incident Assistant"]

  UI["Container: Dashboard UI<br/>Lightweight HTML and JS<br/>Explore logs, anomalies, clusters, stats"]
  API["Container: API Service<br/>FastAPI REST endpoints<br/>Upload, query, admin operations"]
  WORKER["Container: Background Processor<br/>Async parsing and analytics jobs<br/>BackgroundTasks or worker script<br/>Optional APScheduler"]
  ML["Container: Analytics Engine<br/>Anomaly detection and clustering<br/>Isolation Forest or LOF<br/>TF-IDF or embeddings<br/>KMeans or HDBSCAN"]
  AUTH["Container: Auth Module (Optional)<br/>JWT or API keys<br/>RBAC: Admin and Viewer"]
  ALERTS["Container: Alert Service (Optional)<br/>Severity threshold triggers<br/>Email or webhook stub"]
  OBS["Container: Observability<br/>App logs, runtimes, errors with tracebacks"]
  DB["Container: PostgreSQL<br/>Tables: log_files, log_entries, anomalies, error_clusters<br/>Also: users, api_keys, alerts, pipeline_runs<br/>Migrations: Alembic"]

end

%% Relationships
U --> UI
U --> API

S1 --> API
S2 --> API
S3 --> API

UI -->|Calls REST endpoints: logs, stats, anomalies, clusters| API

API -->|Optional auth checks| AUTH
AUTH --> DB

API -->|POST logs upload<br/>Validate size and extension<br/>Create log_files record| DB
API -->|Enqueue async processing<br/>Idempotent per uploaded file| WORKER

WORKER -->|Parse and normalize<br/>Never lose data: store raw_line on failures| DB
WORKER -->|Run after ingestion or on schedule<br/>Job tracking| DB
WORKER --> ML

ML -->|Write anomalies: window, score, features, description| DB
ML -->|Write clusters: label, example, count, last seen| DB
ML -->|Trigger alert when severe| ALERTS

ALERTS -->|Persist alert events and status| DB

API --> OBS
WORKER --> OBS
ML --> OBS
OBS -->|Upload events, runtimes, errors| DB

API -->|Browse and filter logs with pagination<br/>Time range, level, service, source, environment, keyword| DB
API -->|Summary stats<br/>Totals, by level, top services, anomaly count| DB
API -->|Admin rebuild analytics| WORKER
