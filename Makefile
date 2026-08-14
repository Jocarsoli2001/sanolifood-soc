SHELL := /bin/bash

.PHONY: bootstrap config build up down logs ps health test migrate validate clean

bootstrap:
	@test -f .env || (cp .env.example .env && echo "Created .env; replace placeholder secrets before starting.")

config:
	docker compose config --quiet

build:
	docker compose build --pull

up: config
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=150

ps:
	docker compose ps

health:
	@./infrastructure/scripts/healthcheck.sh

test:
	docker compose run --rm --no-deps app pytest -q

migrate:
	docker compose run --rm app alembic upgrade head

validate: config test

clean:
	docker compose down --remove-orphans

