SHELL := /bin/bash

.PHONY: bootstrap config build up down logs ps health test migrate validate rebuild \
	upgrade-0.3 upgrade-0.4 upgrade-0.5 upgrade-0.6 upgrade-0.7 upgrade-0.8 evidence-business reset-lab clean \
	wazuh-preflight wazuh-bootstrap wazuh-up wazuh-down wazuh-ps wazuh-logs \
	wazuh-health wazuh-reload-rules wazuh-test-rules wazuh-credentials evidence-wazuh \
	suricata-preflight suricata-discover suricata-bootstrap suricata-up suricata-down \
	suricata-ps suricata-logs suricata-health suricata-config-test \
	suricata-test-rules suricata-check-live evidence-ndr \
	endpoint-preflight endpoint-configure endpoint-registration-password \
	endpoint-install-ubuntu endpoint-stage-windows endpoint-health \
	endpoint-test-rules endpoint-check-live evidence-endpoint \
	soar-static-check soar-prepare soar-preflight soar-bootstrap soar-up soar-down soar-ps soar-logs \
	soar-health soar-install-workflows soar-disable-integration soar-incidents \
	soar-show soar-approve soar-reject soar-rollback soar-retry soar-metrics \
	soar-validate-live soar-enable-live soar-disable-live soar-backup evidence-soar \
	eval-static-check eval-test eval-list eval-preflight eval-run eval-decide eval-refresh eval-summary evidence-evaluation \
	soc-up soc-health

bootstrap:
	@test -f .env || (cp .env.example .env && echo "Created .env; replace placeholder secrets before starting.")

config:
	docker compose config --quiet

build:
	docker compose build --pull

up: config
	docker compose up -d --build --wait --wait-timeout 240

down:
	docker compose down

logs:
	docker compose logs -f --tail=150

ps:
	docker compose ps

health:
	@./infrastructure/scripts/healthcheck.sh

test:
	docker compose run --rm --no-deps \
		-e DATABASE_URL=sqlite+pysqlite:///:memory: \
		-e APP_ENV=test \
		--entrypoint pytest app -q

migrate:
	docker compose run --rm app alembic upgrade head

validate: config test soar-static-check eval-static-check eval-test

rebuild: config
	docker compose down --remove-orphans
	docker compose build --no-cache --pull app
	docker compose up -d --wait --wait-timeout 240
	@./infrastructure/scripts/healthcheck.sh
	docker compose exec -T app python -m sanolifood.schema_guard

upgrade-0.3:
	@./infrastructure/scripts/upgrade-v0.3.0.sh

upgrade-0.4:
	@./infrastructure/scripts/upgrade-v0.4.0.sh

upgrade-0.5:
	@./infrastructure/scripts/upgrade-v0.5.0.sh

upgrade-0.6:
	@./infrastructure/scripts/upgrade-v0.6.0.sh

upgrade-0.7:
	@./infrastructure/scripts/upgrade-v0.7.0.sh

upgrade-0.8:
	@./infrastructure/scripts/upgrade-v0.8.0.sh

evidence-business:
	@./infrastructure/scripts/collect-business-evidence.sh

wazuh-preflight:
	@./wazuh/scripts/preflight.sh

wazuh-bootstrap wazuh-up:
	@docker volume inspect sanolifood_suricata_logs >/dev/null 2>&1 || docker volume create sanolifood_suricata_logs >/dev/null
	@./wazuh/scripts/bootstrap.sh

wazuh-down:
	@./wazuh/scripts/down.sh

wazuh-ps:
	@docker compose --env-file wazuh/runtime/.env -f wazuh/compose.yaml ps

wazuh-logs:
	@docker compose --env-file wazuh/runtime/.env -f wazuh/compose.yaml logs -f --tail=150

wazuh-health:
	@./wazuh/scripts/healthcheck.sh

wazuh-reload-rules:
	@./wazuh/scripts/reload-rules.sh

wazuh-test-rules:
	@./wazuh/scripts/test-rules.sh

wazuh-credentials:
	@./wazuh/scripts/credentials.sh

evidence-wazuh:
	@./wazuh/scripts/collect-evidence.sh

suricata-preflight:
	@./suricata/scripts/preflight.sh

suricata-discover:
	@./suricata/scripts/discover-network.sh

suricata-bootstrap suricata-up:
	@./suricata/scripts/bootstrap.sh

suricata-down:
	@./suricata/scripts/down.sh

suricata-ps:
	@./suricata/scripts/ps.sh

suricata-logs:
	@./suricata/scripts/logs.sh

suricata-health:
	@./suricata/scripts/healthcheck.sh

suricata-config-test:
	@./suricata/scripts/config-test.sh

suricata-test-rules:
	@./suricata/scripts/test-rules.sh

suricata-check-live:
	@./suricata/scripts/check-live-validation.sh

evidence-ndr:
	@./suricata/scripts/collect-evidence.sh

endpoint-preflight:
	@./endpoints/scripts/preflight.sh

endpoint-configure:
	@./endpoints/scripts/configure-groups.sh

endpoint-registration-password:
	@./endpoints/scripts/registration-password.sh

endpoint-install-ubuntu:
	@sudo ./endpoints/scripts/install-ubuntu-agent.sh

endpoint-stage-windows:
	@test -n "$(WINDOWS_SSH)" || (echo "Use: make endpoint-stage-windows WINDOWS_SSH=usuario@10.20.0.20"; exit 2)
	@./endpoints/scripts/stage-windows.sh "$(WINDOWS_SSH)"

endpoint-health:
	@./endpoints/scripts/healthcheck.sh

endpoint-test-rules:
	@./wazuh/scripts/test-rules.sh

endpoint-check-live:
	@./endpoints/scripts/check-live.sh

evidence-endpoint:
	@WINDOWS_SSH="$(WINDOWS_SSH)" ./endpoints/scripts/collect-evidence.sh

soar-static-check:
	@python3 ./n8n/scripts/validate-static.py

soar-prepare:
	@./n8n/scripts/prepare-runtime.sh

soar-preflight:
	@./n8n/scripts/preflight.sh

soar-bootstrap soar-up:
	@./n8n/scripts/bootstrap.sh

soar-down:
	@./n8n/scripts/down.sh

soar-ps:
	@./n8n/scripts/ps.sh

soar-logs:
	@./n8n/scripts/logs.sh

soar-health:
	@./n8n/scripts/healthcheck.sh

soar-install-workflows:
	@./n8n/scripts/install-workflows.sh

soar-disable-integration:
	@./n8n/scripts/disable-integration.sh

soar-incidents:
	@python3 ./n8n/tools/soar_client.py list

soar-show:
	@test -n "$(INCIDENT_ID)" || (echo "Use: make soar-show INCIDENT_ID=uuid"; exit 2)
	@python3 ./n8n/tools/soar_client.py show "$(INCIDENT_ID)"

soar-approve:
	@test -n "$(INCIDENT_ID)" -a -n "$(ANALYST)" -a -n "$(REASON)" || \
		(echo "Use: make soar-approve INCIDENT_ID=uuid ANALYST=nombre REASON='justificación'"; exit 2)
	@python3 ./n8n/tools/soar_client.py approve "$(INCIDENT_ID)" \
		--analyst "$(ANALYST)" --reason "$(REASON)"

soar-reject:
	@test -n "$(INCIDENT_ID)" -a -n "$(ANALYST)" -a -n "$(REASON)" || \
		(echo "Use: make soar-reject INCIDENT_ID=uuid ANALYST=nombre REASON='justificación'"; exit 2)
	@python3 ./n8n/tools/soar_client.py reject "$(INCIDENT_ID)" \
		--analyst "$(ANALYST)" --reason "$(REASON)"

soar-rollback:
	@test -n "$(ACTION_ID)" -a -n "$(ANALYST)" || \
		(echo "Use: make soar-rollback ACTION_ID=uuid ANALYST=nombre"; exit 2)
	@python3 ./n8n/tools/soar_client.py rollback "$(ACTION_ID)" --analyst "$(ANALYST)"

soar-retry:
	@test -n "$(ACTION_ID)" -a -n "$(ANALYST)" || \
		(echo "Use: make soar-retry ACTION_ID=uuid ANALYST=nombre"; exit 2)
	@python3 ./n8n/tools/soar_client.py retry "$(ACTION_ID)" --analyst "$(ANALYST)"

soar-metrics:
	@python3 ./n8n/tools/soar_client.py metrics

soar-validate-live:
	@python3 ./n8n/tools/soar_client.py validate

soar-enable-live:
	@test "$(CONFIRM)" = "live" || (echo "Use: make soar-enable-live CONFIRM=live"; exit 2)
	@./n8n/scripts/enable-live-responses.sh --confirm

soar-disable-live:
	@./n8n/scripts/disable-live-responses.sh

soar-backup:
	@./n8n/scripts/backup.sh

evidence-soar:
	@./n8n/scripts/collect-evidence.sh

eval-static-check:
	@python3 ./evaluation/scripts/validate-static.py

eval-test:
	@python3 -m unittest discover -s evaluation/tests -p 'test_*.py' -v

eval-list:
	@python3 ./evaluation/tools/evalctl.py list

eval-preflight:
	@python3 ./evaluation/tools/evalctl.py preflight \
		$(if $(KALI_SSH),--kali-ssh "$(KALI_SSH)",) \
		$(if $(WINDOWS_SSH),--windows-ssh "$(WINDOWS_SSH)",)

eval-run:
	@test -n "$(SCENARIO)" || \
		(echo "Use: make eval-run SCENARIO=SCN-001 KALI_SSH=usuario@10.20.0.30"; exit 2)
	@python3 ./evaluation/tools/evalctl.py run --scenario "$(SCENARIO)" \
		$(if $(KALI_SSH),--kali-ssh "$(KALI_SSH)",) \
		$(if $(WINDOWS_SSH),--windows-ssh "$(WINDOWS_SSH)",) \
		$(if $(TIMEOUT),--timeout "$(TIMEOUT)",) \
		$(if $(filter live,$(CONFIRM)),--allow-live,)

eval-decide:
	@test -n "$(RUN_ID)" -a -n "$(DECISION)" -a -n "$(ANALYST)" -a -n "$(REASON)" || \
		(echo "Use: make eval-decide RUN_ID=... DECISION=approve ANALYST=nombre REASON='justificación'"; exit 2)
	@python3 ./evaluation/tools/evalctl.py decide \
		--run-id "$(RUN_ID)" --decision "$(DECISION)" \
		--analyst "$(ANALYST)" --reason "$(REASON)" \
		$(if $(filter live,$(CONFIRM)),--allow-live,)

eval-refresh:
	@test -n "$(RUN_ID)" || (echo "Use: make eval-refresh RUN_ID=..."; exit 2)
	@python3 ./evaluation/tools/evalctl.py refresh --run-id "$(RUN_ID)"

eval-summary:
	@python3 ./evaluation/tools/evalctl.py summary

evidence-evaluation:
	@./evaluation/scripts/collect-evidence.sh

soc-up:
	@$(MAKE) soar-prepare
	@$(MAKE) up
	@$(MAKE) suricata-up
	@$(MAKE) wazuh-up
	@$(MAKE) soar-up

soc-health:
	@$(MAKE) health
	@$(MAKE) wazuh-health
	@$(MAKE) suricata-health
	@$(MAKE) endpoint-health
	@$(MAKE) soar-health

reset-lab:
	@./infrastructure/scripts/reset-lab.sh --confirm

clean:
	docker compose down --remove-orphans
