#!/usr/bin/env bash
set -Eeuo pipefail

integration_source="/wazuh-config-mount/integrations/custom-sanolifood-soar"
secret_source="/wazuh-config-mount/soar/webhook.secret"
state_source="/wazuh-config-mount/soar/integration.state"
manager_config="/var/ossec/etc/ossec.conf"

install -o root -g wazuh -m 0750 \
  "$integration_source" /var/ossec/integrations/custom-sanolifood-soar
install -d -o root -g wazuh -m 0750 /var/ossec/etc/soar
install -o root -g wazuh -m 0640 "$secret_source" /var/ossec/etc/soar/webhook.secret

integration_state="$(tr -d '[:space:]' < "$state_source")"
SOAR_INTEGRATION_STATE="$integration_state" python3 - "$manager_config" <<'PY'
import os
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
content = config_path.read_text(encoding="utf-8")
block_pattern = re.compile(
    r"\n?\s*<!-- SANOLIFOOD_SOAR_BEGIN -->.*?<!-- SANOLIFOOD_SOAR_END -->\s*\n?",
    re.DOTALL,
)
content = block_pattern.sub("\n", content)

if os.environ.get("SOAR_INTEGRATION_STATE") == "enabled":
    integration = """
  <!-- SANOLIFOOD_SOAR_BEGIN -->
  <integration>
    <name>custom-sanolifood-soar</name>
    <hook_url>http://n8n:5678/webhook/sanolifood/wazuh-alert</hook_url>
    <api_key>runtime-secret-file</api_key>
    <rule_id>110011,110012,110020,110030,110040,110100,110110,110120,110130,110140,110200,110210,110211,110220</rule_id>
    <alert_format>json</alert_format>
    <timeout>8</timeout>
    <retries>3</retries>
  </integration>
  <!-- SANOLIFOOD_SOAR_END -->
"""
    closing = "</ossec_config>"
    if closing not in content:
        raise SystemExit("Wazuh ossec.conf has no closing ossec_config element")
    content = content.replace(closing, integration + closing, 1)

config_path.write_text(content, encoding="utf-8")
PY

chown root:wazuh "$manager_config"
chmod 0660 "$manager_config"
