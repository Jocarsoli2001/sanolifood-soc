import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in STANDARD_RECORD_FIELDS and key not in {"message", "asctime"}:
                # Wazuh's stock Suricata rule 86600 claims JSON documents that
                # contain both timestamp and event_type. Namespace the wire
                # field while keeping event_type unchanged in application code
                # and in the transactional audit model.
                payload["sf_event_type" if key == "event_type" else key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str, log_file: str | None = None) -> None:
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        destination = Path(log_file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(destination, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level.upper())
