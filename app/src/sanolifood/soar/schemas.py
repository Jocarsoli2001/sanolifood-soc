from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    workflow_version: Literal["0.7.0"]
    dedup_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_alert_id: str | None = Field(default=None, max_length=128)
    rule_id: int
    rule_level: int = Field(ge=0, le=16)
    rule_description: str = Field(min_length=1, max_length=1000)
    priority: Literal["low", "medium", "high", "critical"]
    playbook_id: str = Field(pattern=r"^PB-[A-Z0-9-]+$")
    agent_id: str | None = Field(default=None, max_length=32)
    agent_name: str | None = Field(default=None, max_length=128)
    source_ip: str | None = Field(default=None, max_length=64)
    actor_username: str | None = Field(default=None, max_length=128)
    resource_path: str | None = Field(default=None, max_length=2048)
    detected_at: datetime
    received_at: datetime
    raw_alert: dict[str, Any]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    analyst: str = Field(min_length=3, max_length=128)
    reason: str = Field(min_length=8, max_length=500)
    nonce: str = Field(min_length=8, max_length=128)
    requested_at: datetime


class OrchestrationErrorRequest(BaseModel):
    workflow_id: str | None = Field(default=None, max_length=128)
    workflow_name: str | None = Field(default=None, max_length=255)
    execution_id: str | None = Field(default=None, max_length=128)
    error_message: str = Field(min_length=1, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)
