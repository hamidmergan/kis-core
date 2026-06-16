# KIS test runner. Run `make` or `make help` for the list of targets.
#
# Two fast UNIT suites (no live stack needed):
#   - backend  : pytest INSIDE the kis-backend container (local Python is too old
#                — the code needs 3.10+, the container ships 3.11).
#   - frontend : Vitest on the host (pure-logic units, node environment).
# One slow E2E suite: Playwright on the host, needs the live stack up
#   (frontend :3000, backend :8000).

BACKEND_CONTAINER ?= kis-backend

# LDAP user backup/restore (acts on the kis-openldap container where make runs:
# locally against your dev stack, on the prod box against prod).
LDAP_CONTAINER ?= kis-openldap
LDAP_ADMIN_DN  ?= cn=admin,dc=th-luebeck,dc=de
LDAP_ADMIN_PW  ?= admin
LDAP_PEOPLE_DN ?= ou=people,dc=th-luebeck,dc=de
LDAP_BACKUP    ?= private/ldap-users.ldif

.DEFAULT_GOAL := help
.PHONY: help test test-backend test-frontend test-unit test-e2e test-all ldap-snapshot ldap-restore

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

ldap-snapshot: ## Save all LDAP users (uid, name, password hash) to $(LDAP_BACKUP)
	@docker ps --format '{{.Names}}' | grep -qx $(LDAP_CONTAINER) \
		|| { echo "✗ $(LDAP_CONTAINER) is not running. Start the stack first."; exit 1; }
	@mkdir -p $(dir $(LDAP_BACKUP))
	@docker exec $(LDAP_CONTAINER) ldapsearch -x -LLL -H ldap://localhost \
		-D '$(LDAP_ADMIN_DN)' -w '$(LDAP_ADMIN_PW)' \
		-b '$(LDAP_PEOPLE_DN)' '(objectClass=*)' > $(LDAP_BACKUP)
	@echo "✓ Saved $$(grep -c '^dn: uid=' $(LDAP_BACKUP)) users to $(LDAP_BACKUP)"

ldap-restore: ## Re-import users from $(LDAP_BACKUP) into LDAP (existing ones are skipped)
	@docker ps --format '{{.Names}}' | grep -qx $(LDAP_CONTAINER) \
		|| { echo "✗ $(LDAP_CONTAINER) is not running. Start the stack first."; exit 1; }
	@test -f $(LDAP_BACKUP) || { echo "✗ $(LDAP_BACKUP) not found. Run 'make ldap-snapshot' first."; exit 1; }
	@docker exec -i $(LDAP_CONTAINER) ldapadd -c -x -H ldap://localhost \
		-D '$(LDAP_ADMIN_DN)' -w '$(LDAP_ADMIN_PW)' < $(LDAP_BACKUP) \
		|| true
	@echo "✓ Restore from $(LDAP_BACKUP) done (already-existing entries were skipped)"
