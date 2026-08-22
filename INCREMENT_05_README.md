# SanoliFood SOC increment v0.5.0

This overlay adds a containerized Suricata 8.0.6 IDS sensor and connects its
EVE JSON telemetry to the existing Wazuh 4.14.7 manager.

## Preconditions

- The repository is at tag v0.4.0 on branch `feature/suricata-ndr`.
- Application, PostgreSQL, Nginx, and Wazuh are healthy.
- The package is copied to the Ubuntu VM but has not been committed.

## Import

```bash
cd ~/sanolifood-soc
IMPORT_DIR="$(mktemp -d)"
unzip -q ~/SanoliFood_Increment_v0.5.0.zip -d "$IMPORT_DIR"
cp -a "$IMPORT_DIR/SanoliFood_Increment_v0.5.0/." .
chmod +x infrastructure/scripts/*.sh wazuh/scripts/*.sh suricata/scripts/*.sh
git diff --check
make suricata-preflight
make upgrade-0.5
```

Do not commit until the unit checks and the live validation described in
`docs/IMPLEMENTATION-05-suricata-ndr.md` pass.

## Security properties

- IDS only: no inline blocking and no packet modification.
- Only required capture capabilities are added.
- Runtime interface data is ignored by Git.
- EVE is persistent and mounted read-only in Wazuh.
- Local rules and mappings are versioned and tested.
- Suricata is limited to 1 GiB RAM and 1.5 CPUs.
