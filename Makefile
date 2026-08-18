SHELL := /bin/bash

.PHONY: bootstrap config build up down logs ps health test migrate validate rebuild upgrade-0.3 evidence-business reset-lab clean

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

evidence-business:
	@./infrastructure/scripts/collect-business-evidence.sh

reset-lab:
	@./infrastructure/scripts/reset-lab.sh --confirm

clean:
	docker compose down --remove-orphans
