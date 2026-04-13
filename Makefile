.PHONY: dev dev-web dev-server test lint format install setup clean docker-up docker-down

dev:
	@trap 'kill 0' EXIT; \
	cd server && .venv/bin/uvicorn main:app --reload --port 8000 & \
	pnpm --filter web dev & \
	wait

dev-web:
	pnpm dev:web

dev-server:
	cd server && .venv/bin/uvicorn main:app --reload --port 8000

test:
	pnpm test

lint:
	pnpm lint

format:
	pnpm format

install:
	pnpm install
	cd server && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

setup: install
	cp -n server/.env.example server/.env || true
	cp -n web/.env.example web/.env || true
	pnpm lefthook install

clean:
	rm -rf node_modules web/.next web/node_modules server/.venv server/__pycache__

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down
