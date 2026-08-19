#!/usr/bin/env bash
set -Eeuo pipefail

chown wazuh:wazuh /var/ossec/etc/rules/sanolifood_rules.xml
chmod 0660 /var/ossec/etc/rules/sanolifood_rules.xml
chown root:wazuh /var/ossec/etc/authd.pass
chmod 0640 /var/ossec/etc/authd.pass
