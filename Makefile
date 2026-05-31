# KIS test runner. Run `make` or `make help` for the list of targets.
#
# Two fast UNIT suites (no live stack needed):
#   - backend  : pytest INSIDE the kis-backend container (local Python is too old
#                — the code needs 3.10+, the container ships 3.11).
#   - frontend : Vitest on the host (pure-logic units, node environment).
# One slow E2E suite: Playwright on the host, needs the live stack up
#   (frontend :3000, backend :8000).

BACKEND_CONTAINER ?= kis-backend

.DEFAULT_GOAL := help
.PHONY: help test test-backend test-frontend test-unit test-e2e test-all

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test: test-unit ## Alias for test-unit (the fast default suites)

test-unit: ## Run both fast unit suites (backend + frontend), no live stack needed
	@$(MAKE) test-backend
	@$(MAKE) test-frontend

test-backend: ## Run backend pytest in the kis-backend container. Pass args via ARGS=...
	@docker ps --format '{{.Names}}' | grep -qx $(BACKEND_CONTAINER) \
		|| { echo "✗ $(BACKEND_CONTAINER) is not running. Start the stack first (docker compose -f docker-compose.dev.yml up -d)."; exit 1; }
	docker exec $(BACKEND_CONTAINER) python -m pytest tests/ $(ARGS)

test-frontend: ## Run frontend Vitest unit tests on the host
	cd frontend && npm test

test-e2e: ## Run frontend Playwright E2E tests (needs the live stack up)
	cd frontend && npm run test:e2e -- $(ARGS)

test-all: ## Run all unit suites (backend + frontend), then E2E
	@$(MAKE) test-unit
	@$(MAKE) test-e2e
