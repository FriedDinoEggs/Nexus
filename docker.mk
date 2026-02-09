PROJ_NAME ?= tt-test
ENV ?= test
GIT_TAG := $(shell git describe --tags --abbrev=0 2>/dev/null || echo 'latest')
VERSION := $(GIT_TAG)
COMPOSE_FILE = compose.yaml

ifeq ($(ENV), prod)
	PROJ_NAME = tt-prod
	COMPOSE_FILE = compose.prod.yaml
endif

DOCKER_CMD := GIT_TAG=$(GIT_TAG) docker compose -f $(COMPOSE_FILE) -p $(PROJ_NAME)

.PHONY: dk-up dk-down dk-dev deploy

dk-up:
	@if [ "$(ENV)" = "prod" ]; then \
		$(DOCKER_CMD) build; \
	fi
	$(DOCKER_CMD) up -d

dk-dev:
	$(DOCKER_CMD) up -d --build

dk-down:
	$(DOCKER_CMD) down -t 30 --remove-orphans

deploy:
	$(DOCKER_CMD) build
	$(DOCKER_CMD) up -d
