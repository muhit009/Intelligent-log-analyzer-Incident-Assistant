# End-to-End System Flow

```mermaid
sequenceDiagram
  autonumber
  participant U as User/Admin
  participant UI as Dashboard UI
  participant API as FastAPI REST API
  participant AUTH as Auth/RBAC (optional)
  participant DB as PostgreSQL
  participant W as Background Worker/Tasks
  participant ML as Analytics Engine
  participant AL as Alert Service (optional)

  %% -------------------------
  %% Flow A: Upload -> Ingest
  %% -------------------------
  rect rgb(235,245,255)
    note over U,ML: Flow A — Upload -> Ingest (batch upload, async processing)
    U->>API: POST /logs/upload (file + metadata: source, env, log_type)
    opt Auth enabled
      API->>AUTH: Verify JWT/API key + role
      AUTH-->>API: Allowed (Admin/Viewer)
    end
    API->>DB: INSERT log_files (status=uploaded, upload_time, metadata)
    API-->>U: 202 Accepted (log_file_id)
    API->>W: Enqueue parse job (log_file_id)

    W->>DB: UPDATE log_files (status=processing)
    W->>W: Read file lines
    W->>W: Parse/normalize line (or keep raw_line)
    W->>DB: INSERT log_entries (structured fields + raw_line)
    alt Parse completed
      W->>DB: UPDATE log_files (status=processed, parse_error_count, confidence)
    else Parse failed
      W->>DB: UPDATE log_files (status=failed, error details)
    end
  end

  %% -------------------------
  %% Flow B: Analytics
  %% -------------------------
  rect rgb(240,255,240)
    note over U,ML: Flow B — Analytics (after ingest or scheduled)
    W->>ML: Start analytics run (range=last 24h or configured)
    ML->>DB: SELECT bucketed features from log_entries (1–2 min windows)
    ML->>ML: Anomaly detection (Isolation Forest / LOF)
    ML->>DB: UPSERT anomalies (window, score, features, description)

    ML->>DB: SELECT error messages for clustering
    ML->>ML: Vectorize (TF-IDF / embeddings)
    ML->>ML: Cluster (KMeans / HDBSCAN)
    ML->>DB: UPSERT error_clusters (label, example, count, last_seen)

    opt Alerts enabled
      ML->>AL: Trigger alert if severity >= threshold
      AL->>DB: INSERT alerts (event, status)
    end

    ML->>DB: INSERT pipeline_runs (analytics runtime, errors if any)
  end

  %% -------------------------
  %% Flow C: Query & Dashboard
  %% -------------------------
  rect rgb(255,248,235)
    note over UI,DB: Flow C — Query & Dashboard
    UI->>API: GET /stats/summary (time range)
    opt Auth enabled
      API->>AUTH: Verify Viewer/Admin
      AUTH-->>API: Allowed
    end
    API->>DB: Aggregate totals, by-level, top services, anomaly count
    API-->>UI: Stats payload

    UI->>API: GET /anomalies (time range)
    API->>DB: SELECT anomalies ORDER BY score desc
    API-->>UI: Anomaly list

    UI->>API: GET /clusters (time range)
    API->>DB: SELECT error_clusters ORDER BY count desc
    API-->>UI: Cluster list

    UI->>API: GET /logs (filters + pagination)
    API->>DB: SELECT log_entries WHERE filters ORDER BY timestamp LIMIT/OFFSET
    API-->>UI: Paginated logs

    UI->>API: GET /logs (anomaly window start/end)
    API->>DB: SELECT log_entries in that time window
    API-->>UI: Logs around anomaly
  end
