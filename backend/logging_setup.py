# logging_setup.py
"""Structured (JSON) logging with a per-request correlation ID.

Every log line becomes one JSON object (timestamp, level, logger name,
message, request_id) instead of a free-text line, so logs are directly
greppable/parseable by a log aggregator (CloudWatch, Datadog, etc.) —
`jq 'select(.request_id == "...")'` finds every log line for one
request across every module that touched it, which a free-text
"%(asctime)s [%(name)s] ..." format can't do without regex.

request_id is threaded through via a contextvar rather than passed
explicitly to every logger call site: RequestIdMiddleware (main.py)
sets it once per request, and every existing logger.info()/.warning()
call anywhere in the codebase — no call site changes needed — picks it
up automatically through the logging Filter below.
"""
import contextvars
import json
import logging

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root logger's handlers with one JSON-structured,
    request-ID-tagged stream handler. Call once at process startup."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
