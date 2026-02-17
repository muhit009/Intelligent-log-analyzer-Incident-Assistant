# Parsing & Normalization Strategy (v1)

This document defines the **parsing contract** and **normalized schema** for the Intelligent Log Analyzer. The goal is to ingest log files from multiple sources, parse them into a consistent structure, and **never lose data** even when parsing fails.

---

## 1. Scope (v1)

### Supported log formats (v1)
We support **two primary formats** in v1:

1. **Application-style logs (AppLog)**
   - Format: ISO timestamp + log level + service + message
   - Example:
     - `2025-12-31T12:15:41Z INFO auth-service User login succeeded user_id=42`
     - `2025-12-31 12:15:41,120 ERROR billing Failed to charge card: timeout`

2. **HTTP access logs (AccessLog)**
   - Intended for NASA HTTP logs and common Apache/Nginx formats (Common/Combined-like).
   - Example:
     - `127.0.0.1 - - [31/Dec/2025:12:15:41 +0000] "GET /api/v1/health HTTP/1.1" 200 123 "-" "curl/7.88.1"`

> Non-goal (v1): Fully universal parsing for arbitrary log formats. Unknown formats are still stored as raw lines and marked as failed/partial.

---

## 2. Design Principles

### P0: Never lose data
- Every input line MUST result in a persisted `log_entries` record.
- If parsing fails, we store `raw_line` and mark the entry as failed.

### P1: Best-effort normalization
- Attempt to extract `timestamp`, `level`, `service`, and `message`.
- Missing fields are allowed and represented as `NULL` (or equivalent).

### P2: Deterministic + idempotent ingestion
- Re-processing the same uploaded file should not create duplicates.
- Each line is uniquely identified by `(log_file_id, line_number)`.

### P3: Traceability
- Each normalized entry maintains a link to its source file, original line number, and raw text.

---

## 3. Normalized Schema Contract

### `log_files` (file-level metadata)
Each uploaded file creates a `log_files` record used for job tracking and traceability.

**Core fields**
- `id` (PK)
- `filename` (original name)
- `stored_path` (server path or object store path)
- `source` (string; e.g., nginx, app, nasa_http)
- `environment` (string; e.g., dev, staging, prod)
- `log_type` (string; e.g., app, access)
- `status` (enum/string): `uploaded | processing | processed | failed`

**Processing summary fields**
- `total_lines` (int)
- `parsed_lines` (int)
- `failed_lines` (int)
- `processed_at` (datetime, nullable)
- `error` (text, nullable)

---

### `log_entries` (normalized line-level records)
Every line becomes one `log_entries` row.

**Required fields (always populated)**
- `id` (PK)
- `log_file_id` (FK → log_files.id)
- `line_number` (int; 1-based)
- `raw_line` (text; original unmodified line)
- `parse_status` (enum/string): `parsed | partial | failed`

**Optional normalized fields**
- `timestamp` (datetime, nullable)
- `level` (string, nullable; normalized to uppercase when present)
- `service` (string, nullable)
- `message` (text, nullable)

**Debug/quality fields**
- `parse_confidence` (float 0.0–1.0, nullable)
- `parse_error` (text, nullable)
- `parser_name` (string, nullable; e.g., "app_v1", "access_combined_v1")

---

## 4. Parsing Outcomes & Status Semantics

### `parse_status = parsed`
- All key fields are present and valid for the detected format.
- AppLog: timestamp + level + service + message extracted.
- AccessLog: timestamp + request + status extracted (at minimum), plus other optional fields.

### `parse_status = partial`
- Line resembles a supported format but one or more key fields are missing/invalid.
- Example: timestamp parsed but level missing, or access log request malformed.

### `parse_status = failed`
- Line does not match supported formats OR parsing raised an exception.
- `raw_line` is still stored.
- `parse_error` should include a short reason.

---

## 5. Field Normalization Rules

### Timestamp normalization
- Output timestamps are stored as `datetime`.
- If timezone is present, preserve/convert consistently (recommended: convert to UTC in storage).
- If timestamp cannot be parsed:
  - Set `timestamp = NULL`
  - Mark `parse_status` as `partial` or `failed` depending on match quality

### Level normalization
- Normalize to uppercase when present: `INFO`, `WARN`, `WARNING`, `ERROR`, `DEBUG`, `TRACE`, `CRITICAL`
- Map common variants:
  - `WARN` and `WARNING` may be treated as the same category (implementation choice), but stored consistently.

### Service normalization
- Service names are stored as simple strings (e.g., `auth-service`, `billing`, `api-gateway`).
- If no service exists in the line, store `NULL`.

### Message normalization
- For AppLog, `message` is the remainder of the line after parsed fields.
- For AccessLog, `message` can be a synthesized string or left NULL (v1 choice).
  - Recommended: store the request line (`"GET /path HTTP/1.1"`) into `message`.

---

## 6. Format Detection Strategy (v1)

Detection is **heuristic-based** in v1:

1. Attempt **AppLog parser** first if line begins with an ISO-like timestamp.
2. Attempt **AccessLog parser** if line contains brackets time pattern (`[dd/Mon/yyyy:hh:mm:ss ...]`) or quoted request section.
3. If no parser matches, mark as `failed`.

> Implementation note: Always guard parsers with try/except and return a safe result.

---

## 7. Error Handling & Reliability Guarantees

### Per-line failures
- A single bad line MUST NOT fail the entire file ingestion.
- If parsing a line fails:
  - Insert `log_entries` row with `raw_line`
  - `parse_status = failed`
  - `parse_error` populated with reason

### File-level failures
- If the ingestion job crashes unexpectedly:
  - Mark `log_files.status = failed`
  - Store `log_files.error` (traceback summary)
  - Partial entries already inserted remain valid (append-only design)

---

## 8. Idempotency Strategy

To prevent duplicate ingestion:
- Enforce a unique constraint on `(log_file_id, line_number)`
- Re-processing behavior:
  - If an entry already exists for a given `(log_file_id, line_number)`, skip or upsert consistently.
  - Prefer: delete existing entries for that file and re-insert only if you explicitly support “rebuild ingestion”.

---

## 9. Performance Notes (v1)

- Ingestion reads files as a stream (line-by-line), not fully into memory.
- Batch inserts are recommended (e.g., insert in chunks of 1k–5k lines).
- Create indexes that support querying:
  - `timestamp`
  - `level`
  - `service`
  - `log_file_id`

---

## 10. Testing Checklist (Acceptance)

A file is considered correctly ingested if:
- `log_files` record exists and transitions through `uploaded → processing → processed`
- `total_lines == number of lines read`
- `parsed_lines + failed_lines == total_lines` (with partial counted as parsed or separately tracked)
- `log_entries` has exactly `total_lines` rows for that file
- Queries by `timestamp` and `level` return expected entries
- A file with malformed lines still results in stored `raw_line` rows and does not crash the job

---

## 11. Future Extensions (not required for v1)

- Config-driven parsers per source (regex rules in YAML/JSON)
- Additional access log fields:
  - `http_method`, `path`, `status_code`, `response_bytes`, `user_agent`, `referrer`, `client_ip`
- Parser versioning and reprocessing:
  - store `parser_version` per entry and allow rebuild analytics or rebuild parsing
