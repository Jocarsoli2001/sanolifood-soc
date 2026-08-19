SHELL := /bin/bash

.PHONY: bootstrap config build up down logs ps health test migrate validate rebuild upgrade-0.3 upgrade-0.4 evidence-business reset-lab clean wazuh-preflight wazuh-bootstrap wazuh-up wazuh-down wazuh-ps wazuh-logs wazuh-health wazuh-reload-rules wazuh-test-rules wazuh-credentials evidence-wazuh soc-up soc-health

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

validate: config test

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

evidence-business:
	@./infrastructure/scripts/collect-business-evidence.sh

wazuh-preflight:
	@./wazuh/scripts/preflight.sh

wazuh-bootstrap wazuh-up:
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

soc-up:
	@$(MAKE) up
	@$(MAKE) wazuh-up

soc-health:
	@$(MAKE) health
	@$(MAKE) wazuh-health

reset-lab:
	@./infrastructure/scripts/reset-lab.sh --confirm

clean:
	docker compose down --remove-orphans
