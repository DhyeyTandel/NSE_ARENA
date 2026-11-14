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


KITE_CALLBACK_PREFIX = "/api/kite/callback"
_UVICORN_ACCESS_ARGS_LEN = 5  # (client_addr, method, full_path, http_version, status_code)


class KiteCallbackQueryRedactionFilter(logging.Filter):
    """Redact the query string of Kite login callback requests in the
    uvicorn access log.

    The callback URL carries a one-time request_token and a state value;
    uvicorn logs the full request line, so without this filter those land
    in the logs. Only the query string is replaced; the line is still kept.
    This filter must never raise: any record with an unexpected shape is
    passed through unchanged.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            args = record.args
            if not isinstance(args, tuple) or len(args) != _UVICORN_ACCESS_ARGS_LEN:
                return True
            full_path = args[2]
            if not isinstance(full_path, str):
                return True
            path, sep, _query = full_path.partition("?")
            if not sep or not path.startswith(KITE_CALLBACK_PREFIX):
                return True
            record.args = (*args[:2], f"{path}?[redacted]", *args[3:])
        except Exception:
            return True
        return True


def install_access_log_redaction() -> None:
    """Attach the Kite callback redaction filter to uvicorn's access logger.

    Idempotent. Attaching to the logger object (not a handler) means it
    survives uvicorn's own dictConfig, which runs before the app is imported.
    """
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, KiteCallbackQueryRedactionFilter) for f in access_logger.filters):
        access_logger.addFilter(KiteCallbackQueryRedactionFilter())


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root logger's handlers with one JSON-structured,
    request-ID-tagged stream handler. Call once at process startup.
    Also installs the Kite callback access-log redaction filter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    install_access_log_redaction()
