.PHONY: demo-up demo-down demo-reset demo-status verify verify-db verify-backend verify-frontend verify-browser security

demo-up:
	docker compose up --build --detach --wait
	@curl --fail --silent --show-error http://127.0.0.1:8011/v1/health/ready >/dev/null
	@curl --fail --silent --show-error http://127.0.0.1:3011/healthz >/dev/null
	@printf '%s\n' 'Entity Control Center: http://127.0.0.1:3011' 'API documentation: http://127.0.0.1:8011/docs'

demo-down:
	docker compose down

demo-reset:
	docker compose down --volumes --remove-orphans
	$(MAKE) demo-up

demo-status:
	docker compose ps

verify: verify-backend verify-frontend

verify-db:
	docker compose up --detach --wait postgres
	uv run alembic upgrade head

verify-backend: verify-db
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict src tests scripts/seed_demo.py
	uv run pytest --cov=acquisition_launchpad --cov-fail-under=94
	uv run alembic check

verify-frontend:
	npm --prefix frontend ci
	npm --prefix frontend run typecheck
	npm --prefix frontend run lint
	npm --prefix frontend test
	npm --prefix frontend run build

verify-browser: demo-up
	cd frontend && LAUNCHPAD_E2E_SKIP_WEBSERVER=1 LAUNCHPAD_E2E_WEB_BASE_URL=http://127.0.0.1:3011 LAUNCHPAD_E2E_API_BASE_URL=http://127.0.0.1:8011 npm run test:e2e

security:
	uv run --with pip-audit pip-audit
	npm --prefix frontend audit --audit-level=high
	@command -v gitleaks >/dev/null || { printf '%s\n' 'gitleaks is required for secret scanning'; exit 1; }
	gitleaks dir . --no-banner --redact
