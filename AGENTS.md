# Apt-Chat

A monorepo with a Next.js web app, Python/FastAPI backend, and ETL pipeline.

## Structure

- `web/` - Next.js frontend
- `server/` - Python/FastAPI backend
- `etl/` - Data pipeline

## Commands

```bash
pnpm dev          # Start all services
pnpm dev:web      # Start web only
pnpm dev:server   # Start backend only
pnpm test         # Run all tests
pnpm lint         # Lint all code
pnpm lint:fix     # Fix linting issues
```

## Tech Stack

- **Frontend**: Next.js, TypeScript, React
- **Backend**: Python, FastAPI, Supabase
- **Database**: Supabase (Postgres)
- **Linting**: Biome (JS/TS), Ruff (Python)

<!-- BEGIN:supabase -->
<!-- END:supabase -->
<!-- BEGIN:vercel-react-best-practices -->
<!-- END:vercel-react-best-practices -->
