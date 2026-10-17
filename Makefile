SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:

COMPOSE := docker compose

.PHONY: local-stack-up local-stack-down logs ps restart shell django-shell \
	migrate makemigrations createsuperuser test lint format

local-stack-up:
	$(COMPOSE) up -d --build

local-stack-down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps -a

restart:
	$(COMPOSE) restart web celery_worker nginx

shell:
	$(COMPOSE) exec web bash

django-shell:
	$(COMPOSE) exec web python manage.py shell

migrate:
	$(COMPOSE) exec web python manage.py migrate

makemigrations:
	$(COMPOSE) exec web python manage.py makemigrations

createsuperuser:
	$(COMPOSE) exec web python manage.py createsuperuser

test:
	$(COMPOSE) exec -e DJANGO_SETTINGS_MODULE=config.settings.test web pytest

lint:
	$(COMPOSE) exec web ruff check .

format:
	$(COMPOSE) exec web ruff format .
