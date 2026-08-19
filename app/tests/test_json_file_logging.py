import json
import logging

from sanolifood.core.logging import configure_logging


def test_json_events_can_be_written_to_soc_shared_file(tmp_path):
    destination = tmp_path / "sanolifood.jsonl"
    try:
        configure_logging("INFO", str(destination))
        logging.getLogger("sanolifood.security").info(
            "auth.login.failed",
            extra={
                "event_type": "auth.login.failed",
                "source_ip": "10.20.0.50",
                "correlation_id": "test-correlation-id",
            },
        )
        payload = json.loads(destination.read_text(encoding="utf-8").strip())
        assert payload["sf_event_type"] == "auth.login.failed"
        assert "event_type" not in payload
        assert payload["source_ip"] == "10.20.0.50"
        assert payload["correlation_id"] == "test-correlation-id"
    finally:
        configure_logging("INFO")
