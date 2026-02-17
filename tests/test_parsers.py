"""Pure unit tests for app.services.parsers — no DB required."""
from datetime import datetime

from app.services.parsers import parse_line


class TestAppLogIsoZ:
    def test_full_parse(self):
        result = parse_line("2025-12-31T12:15:41Z INFO auth-service User login ok")
        assert result["parse_status"] == "parsed"
        assert result["parser_name"] == "app_v1"
        assert result["level"] == "INFO"
        assert result["service"] == "auth-service"
        assert result["message"] == "User login ok"
        assert result["timestamp"] == datetime(2025, 12, 31, 12, 15, 41)
        assert result["parse_confidence"] == 0.95

    def test_error_level(self):
        result = parse_line("2025-01-01T00:00:00Z ERROR svc Something broke")
        assert result["level"] == "ERROR"
        assert result["parse_status"] == "parsed"

    def test_fractional_seconds(self):
        result = parse_line("2025-06-15T10:30:00.123456Z WARN api-gw Slow response")
        assert result["parse_status"] == "parsed"
        assert result["timestamp"].microsecond == 123456


class TestAppLogIsoSpace:
    def test_comma_millis(self):
        result = parse_line("2025-12-31 12:15:41,120 ERROR billing Payment failed")
        assert result["parse_status"] == "parsed"
        assert result["level"] == "ERROR"
        assert result["service"] == "billing"
        assert result["timestamp"] == datetime(2025, 12, 31, 12, 15, 41, 120000)

    def test_no_millis(self):
        result = parse_line("2025-12-31 12:15:41 INFO billing Payment ok")
        assert result["parse_status"] == "parsed"
        assert result["timestamp"] == datetime(2025, 12, 31, 12, 15, 41)


class TestAccessLog:
    def test_common_format(self):
        line = '127.0.0.1 - - [31/Dec/2025:12:15:41 +0000] "GET /health HTTP/1.1" 200 15'
        result = parse_line(line)
        assert result["parse_status"] == "parsed"
        assert result["parser_name"] == "access_v1"
        assert result["timestamp"] == datetime(2025, 12, 31, 12, 15, 41)
        assert "GET /health" in result["message"]

    def test_combined_format(self):
        line = '10.0.0.1 - user [31/Dec/2025:12:15:41 +0000] "POST /api HTTP/1.1" 201 42 "http://ref" "Mozilla/5.0"'
        result = parse_line(line)
        assert result["parse_status"] == "parsed"
        assert "POST /api" in result["message"]

    def test_negative_tz_offset(self):
        line = '192.168.1.1 - - [31/Dec/2025:12:15:41 -0500] "GET / HTTP/1.1" 200 0'
        result = parse_line(line)
        assert result["parse_status"] == "parsed"
        # -0500 means local is UTC-5, so UTC = 12:15:41 + 5h = 17:15:41
        assert result["timestamp"] == datetime(2025, 12, 31, 17, 15, 41)


class TestJsonLog:
    def test_full_json(self):
        line = '{"timestamp": "2025-12-31T12:15:42Z", "level": "WARN", "service": "gateway", "message": "High latency"}'
        result = parse_line(line)
        assert result["parse_status"] == "parsed"
        assert result["parser_name"] == "json_v1"
        assert result["level"] == "WARN"
        assert result["service"] == "gateway"
        assert result["message"] == "High latency"
        assert result["parse_confidence"] == 0.95

    def test_variant_field_names(self):
        line = '{"ts": "2025-06-15T10:00:00Z", "severity": "ERROR", "app": "worker", "msg": "OOM killed"}'
        result = parse_line(line)
        assert result["parse_status"] == "parsed"
        assert result["level"] == "ERROR"
        assert result["service"] == "worker"
        assert result["message"] == "OOM killed"

    def test_nested_service(self):
        line = '{"timestamp": "2025-06-15T10:00:00Z", "level": "INFO", "context": {"service": "nested-svc"}, "message": "Hello"}'
        result = parse_line(line)
        assert result["service"] == "nested-svc"
        assert result["parse_status"] == "parsed"

    def test_invalid_json_fallthrough(self):
        line = '{"broken json'
        result = parse_line(line)
        # Should fall through to fallback since it starts with { but isn't valid JSON
        assert result["parser_name"] != "json_v1"
        assert result["parse_status"] == "failed"

    def test_json_no_log_fields(self):
        line = '{"foo": "bar", "count": 42}'
        result = parse_line(line)
        assert result["parser_name"] == "json_v1"
        assert result["parse_confidence"] == 0.5
        assert result["parse_status"] == "partial"

    def test_partial_fields(self):
        line = '{"level": "ERROR", "message": "Something broke"}'
        result = parse_line(line)
        assert result["parser_name"] == "json_v1"
        assert result["parse_confidence"] == 0.7
        assert result["level"] == "ERROR"
        assert result["message"] == "Something broke"


class TestFallback:
    def test_garbage_line(self):
        result = parse_line("this is total garbage 12345")
        assert result["parse_status"] == "failed"
        assert result["parser_name"] is None
        assert result["parse_confidence"] == 0.0

    def test_empty_line(self):
        result = parse_line("")
        assert result["parse_status"] == "failed"

    def test_blank_string(self):
        result = parse_line("   ")
        assert result["parse_status"] == "failed"
