# Implementation 05: Suricata NDR telemetry

## Objective

Add reproducible network detection to SanoliFood without modifying the stable
application. Suricata observes the Ubuntu VM edge interface, writes EVE JSON,
and Wazuh enriches selected signatures with severity and MITRE ATT&CK data.

## Data path

1. Windows or Kali sends traffic to the Ubuntu VM.
2. Suricata observes the packet on the default-route interface.
3. A local signature creates an EVE `alert` event.
4. The named Docker volume persists `eve.json`.
5. Wazuh reads the volume in read-only mode.
6. Wazuh rule 86601 identifies a Suricata alert.
7. SanoliFood rules 110100-110140 assign context, severity, and MITRE mapping.

## Deterministic signatures

| Suricata SID | Wazuh rule | Use case | MITRE ATT&CK |
|---|---:|---|---|
| 9900001 | 110100 | Harmless end-to-end validation header | Not applicable |
| 9900002 | 110110 | TCP service scan threshold | T1046 |
| 9900003 | 110120 | Sensitive web path enumeration | T1595.002 |
| 9900004 | 110130 | SQL injection indicator | T1190 |
| 9900005 | 110140 | High-rate HTTP enumeration | T1595.002 |

## Deployment

```bash
make suricata-preflight
make upgrade-0.5
make suricata-test-rules
make soc-health
```

## Harmless live validation

Run the following from Windows PowerShell, replacing the IP if DHCP changed:

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri "http://192.168.0.23:8080/health/ready" `
  -Headers @{"X-SanoliFood-Lab"="ndr-validation"}
```

Wait approximately 20 seconds and run on Ubuntu:

```bash
make suricata-check-live
```

Expected result:

```text
OK   Suricata EVE     signature_id=9900001
OK   Wazuh alert      rule=110100
PASS live NDR telemetry path: network -> Suricata -> EVE -> Wazuh.
```

This request is a validation marker, not an attack simulation. Kali scenarios
are introduced only after capture and ingestion are proven reliable.

## Evidence NDR-001

After live validation:

```bash
make evidence-ndr
```

Keep these screenshots outside Git and include them in the annex archive:

1. `01-suricata-health.png`: `make suricata-health`.
2. `02-suricata-rule-tests.png`: `make suricata-test-rules`.
3. `03-eve-validation-alert.png`: EVE SID 9900001.
4. `04-wazuh-ndr-validation.png`: Wazuh rule 110100 in Threat Hunting.
5. `05-soc-health-with-ndr.png`: complete `make soc-health` output.
6. `06-resource-usage.png`: `docker stats --no-stream`.

Do not copy `suricata/runtime/.env`, Wazuh credentials, private keys, or the
complete packet log into the public repository.

## Operational commands

```bash
make suricata-ps
make suricata-logs
make suricata-health
make suricata-config-test
make suricata-test-rules
make suricata-down
make suricata-up
```

## References

- Suricata 8.0 documentation: https://docs.suricata.io/en/suricata-8.0.6/
- Suricata EVE JSON: https://docs.suricata.io/en/suricata-8.0.6/output/eve/eve-json-output.html
- Wazuh network IDS integration: https://documentation.wazuh.com/current/proof-of-concept-guide/integrate-network-ids-suricata.html
- MITRE ATT&CK Enterprise techniques: https://attack.mitre.org/techniques/enterprise/
