import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from sanolifood.soar.config import get_soar_settings


SUPPORTED_ACTION_TYPES = frozenset(
    {"collect_evidence", "app_ip_block", "app_account_lock", "quality_guard"}
)


class ActionDefinition(BaseModel):
    type: str
    automatic: bool
    reversible: bool
    ttl_seconds: int | None = None
    target_field: str | None = None
    target_value: str | None = None
    optional: bool = False

    @model_validator(mode="after")
    def validate_action(self):
        if self.type not in SUPPORTED_ACTION_TYPES:
            raise ValueError(f"Unsupported SOAR action type: {self.type}")
        if self.type == "collect_evidence":
            if not self.automatic or self.reversible or self.ttl_seconds is not None:
                raise ValueError("collect_evidence must be automatic and non-reversible")
            return self
        if self.automatic:
            raise ValueError("Containment actions require analyst approval")
        if not self.reversible or self.ttl_seconds is None:
            raise ValueError("Containment actions must be reversible and have a TTL")
        if bool(self.target_field) == bool(self.target_value):
            raise ValueError("Containment actions require exactly one target source")
        return self


class PlaybookDefinition(BaseModel):
    id: str = Field(pattern=r"^PB-[A-Z0-9-]+$")
    name: str
    description: str
    rule_ids: list[int] = Field(min_length=1)
    priority: str
    actions: list[ActionDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_playbook(self):
        if self.priority not in {"low", "medium", "high", "critical"}:
            raise ValueError("Unsupported playbook priority")
        if len(set(self.rule_ids)) != len(self.rule_ids):
            raise ValueError(f"Duplicate rule in playbook {self.id}")
        return self


class PlaybookCatalog(BaseModel):
    schema_version: int
    catalog_version: str
    playbooks: list[PlaybookDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self):
        if self.schema_version != 1:
            raise ValueError("Unsupported playbook catalog schema")
        playbook_ids: set[str] = set()
        rule_ids: set[int] = set()
        for playbook in self.playbooks:
            if playbook.id in playbook_ids:
                raise ValueError(f"Duplicate playbook ID: {playbook.id}")
            playbook_ids.add(playbook.id)
            overlap = rule_ids.intersection(playbook.rule_ids)
            if overlap:
                raise ValueError(f"Rules assigned to multiple playbooks: {sorted(overlap)}")
            rule_ids.update(playbook.rule_ids)
        return self

    def for_rule(self, rule_id: int) -> PlaybookDefinition:
        for playbook in self.playbooks:
            if rule_id in playbook.rule_ids:
                return playbook
        raise KeyError(f"No SOAR playbook is assigned to Wazuh rule {rule_id}")

    @property
    def routed_rule_ids(self) -> list[int]:
        return sorted(rule_id for playbook in self.playbooks for rule_id in playbook.rule_ids)


def load_catalog(path: str | Path) -> PlaybookCatalog:
    catalog_path = Path(path)
    with catalog_path.open("r", encoding="utf-8") as catalog_file:
        payload = json.load(catalog_file)
    catalog = PlaybookCatalog.model_validate(payload)
    max_ttl = get_soar_settings().soar_max_ttl_seconds
    for playbook in catalog.playbooks:
        for action in playbook.actions:
            if action.ttl_seconds is not None and action.ttl_seconds > max_ttl:
                raise ValueError(
                    f"Action {action.type} in {playbook.id} exceeds SOAR_MAX_TTL_SECONDS"
                )
    return catalog


@lru_cache
def get_catalog() -> PlaybookCatalog:
    return load_catalog(get_soar_settings().soar_playbook_catalog)
