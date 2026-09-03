"""Structured JSON logging with per-request request_id."""

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def _add_request_id(_: object, __: str, event_dict: dict) -> dict:
    event_dict["request_id"] = request_id_ctx.get()
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,  # type: ignore[list-item]
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
    )


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    request_id_ctx.set(rid)
    return rid


def get_logger(name: str = "scanner") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
