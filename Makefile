.PHONY: dev dev-web dev-server test lint format install setup clean docker-up docker-down

dev:
	@trap 'kill 0' EXIT; \
	cd apps/server && .venv/bin/uvicorn main:app --reload --port 8000 & \
	pnpm --filter web dev & \
	wait

dev-web:
	pnpm dev:web

dev-server:
	cd apps/server && .venv/bin/uvicorn main:app --reload --port 8000

test:
	pnpm test

lint:
	pnpm lint

format:
	pnpm format

install:
	pnpm install
	cd apps/server && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

setup: install
	cp -n apps/server/.env.example apps/server/.env || true
	cp -n apps/web/.env.example apps/web/.env || true
	pnpm lefthook install

clean:
	rm -rf node_modules apps/web/.next apps/web/node_modules apps/server/.venv apps/server/__pycache__

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down
