setup:
	[ -f backend/.env ] || cp backend/.env.example backend/.env
	[ -f frontend/.env ] || cp frontend/.env.example frontend/.env
	cd frontend && bun install

generate-client:
	cd frontend && bun run generate-client

start-frontend:
	cd frontend && bun run dev

start-backend:
	docker compose up -d

start-celery:
	docker compose --profile celery up -d

# Also stops the Celery services. Volumes are kept, so the database survives.
stop-backend:
	docker compose --profile celery down

test-backend:
	docker compose exec backend python -m pytest

lint-frontend:
	cd frontend && bun run prettier:fix && bun run lint:staged
