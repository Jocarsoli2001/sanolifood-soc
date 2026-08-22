# Validation checklist v0.5.0

## Static validation

- [ ] `git diff --check` reports no errors.
- [ ] `bash -n` succeeds for every new shell script.
- [ ] `make suricata-preflight` identifies the external interface and VM IP.
- [ ] `make suricata-config-test` validates configuration and local rules.
- [ ] `make wazuh-test-rules` passes application and NDR fixtures.

## Runtime validation

- [ ] Suricata container is healthy.
- [ ] `eve.json` exists and is readable.
- [ ] Wazuh manager reads the shared EVE volume.
- [ ] Existing application, database, proxy, and Wazuh services remain healthy.
- [ ] Windows validation request generates Suricata SID 9900001.
- [ ] Wazuh generates custom rule 110100 for the same event.
- [ ] `make suricata-check-live` reports PASS.

## Evidence and release

- [ ] `make evidence-ndr` creates non-empty files in `evidence/NDR-001`.
- [ ] No private keys, runtime environments, credentials, or payloads are staged.
- [ ] Captures are copied to the external evidence archive.
- [ ] Branch is pushed only after review.
- [ ] Merge into `main` is tagged `v0.5.0` after final validation.
