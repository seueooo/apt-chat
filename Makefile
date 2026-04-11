.PHONY: dev dev-web dev-api test lint format install setup clean docker-up docker-down

dev:
	pnpm dev

dev-web:
	pnpm dev:web

dev-api:
	pnpm dev:api

test:
	pnpm test

lint:
	pnpm lint

format:
	pnpm format

install:
	pnpm install
	cd api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

setup: install
	cp -n .env.example .env || true
	pnpm lefthook install

clean:
	rm -rf node_modules web/.next web/node_modules api/.venv api/__pycache__

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down
