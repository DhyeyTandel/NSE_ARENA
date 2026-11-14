# tests/test_access_log_redaction.py
"""Kite login callback URLs carry a one-time request_token and state.
uvicorn's access log writes the full request line, so the query string of
/api/kite/callback requests must be redacted before the record is emitted.
"""
import logging

import main  # noqa: F401  (importing main runs configure_logging at startup)
from logging_setup import (
    KiteCallbackQueryRedactionFilter,
    install_access_log_redaction,
)


def _access_record(full_path, args=None):
    if args is None:
        args = ("127.0.0.1:5000", "GET", full_path, "1.1", 302)
    return logging.LogRecord(
        name="uvicorn.access", level=logging.INFO, pathname=__file__,
        lineno=1, msg='%s - "%s %s HTTP/%s" %d', args=args, exc_info=None,
    )


def _apply(record):
    keep = KiteCallbackQueryRedactionFilter().filter(record)
    return keep, record


def test_kite_callback_query_is_redacted():
    keep, record = _apply(_access_record(
        "/api/kite/callback?action=login&status=success&request_token=XXXX&state=YYYY"
    ))
    assert keep is True
    assert record.args[2] == "/api/kite/callback?[redacted]"
    assert "XXXX" not in record.getMessage()
    assert "YYYY" not in record.getMessage()
    assert record.getMessage().startswith('127.0.0.1:5000 - "GET /api/kite/callback?[redacted] HTTP/1.1" 302')


def test_kite_callback_without_query_is_unchanged():
    original = _access_record("/api/kite/callback")
    before = original.args
    keep, record = _apply(original)
    assert keep is True
    assert record.args == before


def test_other_path_with_query_is_unchanged():
    original = _access_record("/price/RELIANCE?x=1")
    before = original.args
    keep, record = _apply(original)
    assert keep is True
    assert record.args == before
    assert record.args[2] == "/price/RELIANCE?x=1"


def test_unexpected_args_shape_does_not_raise_and_is_kept():
    shapes = [
        None,
        (),
        ("only-one",),
        ("a", "GET", "/api/kite/callback?request_token=XXXX"),  # too short
        ("a", "GET", "/api/kite/callback?request_token=XXXX", "1.1", 302, "extra"),
        ({"full_path": "/api/kite/callback?request_token=XXXX"},),  # mapping args
        ("a", "GET", 12345, "1.1", 302),  # non-string path
    ]
    for args in shapes:
        record = _access_record("/unused", args=args)
        before = record.args
        keep, record = _apply(record)
        assert keep is True, args
        assert record.args == before, args


def test_filter_is_attached_to_uvicorn_access_logger_at_app_startup():
    access_logger = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, KiteCallbackQueryRedactionFilter) for f in access_logger.filters)


def test_install_is_idempotent():
    access_logger = logging.getLogger("uvicorn.access")
    install_access_log_redaction()
    install_access_log_redaction()
    count = sum(isinstance(f, KiteCallbackQueryRedactionFilter) for f in access_logger.filters)
    assert count == 1


def test_filter_survives_uvicorn_style_dict_config():
    """uvicorn applies dictConfig with disable_existing_loggers=False; a
    later dictConfig must not strip the filter from the logger object."""
    import logging.config

    install_access_log_redaction()
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"null": {"class": "logging.NullHandler"}},
        "loggers": {"uvicorn.access": {"handlers": ["null"], "level": "INFO"}},
    })
    access_logger = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, KiteCallbackQueryRedactionFilter) for f in access_logger.filters)
