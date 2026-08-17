import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from sanolifood.models import AuditEvent, User


logger = logging.getLogger("sanolifood.security")


def record_event(
    db: Session,
    *,
    event_type: str,
    outcome: str,
    request: Request | None = None,
    actor: User | None = None,
    actor_username: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    source_ip = "system"
    user_agent: str | None = None
    correlation_id = str(uuid.uuid4())
    if request is not None:
        source_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "unknown")
        user_agent = request.headers.get("User-Agent")
        correlation_id = getattr(request.state, "correlation_id", correlation_id)

    event = AuditEvent(
        actor_user_id=actor.id if actor else None,
        actor_username=actor.username if actor else actor_username,
        event_type=event_type,
        outcome=outcome,
        source_ip=source_ip,
        user_agent=user_agent,
        correlation_id=correlation_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(event)
    logger.info(
        event_type,
        extra={
            "event_type": event_type,
            "outcome": outcome,
            "actor_username": event.actor_username,
            "source_ip": source_ip,
            "correlation_id": correlation_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
        },
    )
    return event
