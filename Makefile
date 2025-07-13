# YudaiV3 Docker Management Makefile
# NOT COMPLETED
# NOT TESTED

.PHONY: help build up down logs restart clean init-db check-db dev-up dev-down dev-logs

# Default target
help:
	@echo "YudaiV3 Docker Management"
	@echo "========================="
	@echo "Production Commands:"
	@echo "  make build     - Build all Docker images"
	@echo "  make up        - Start all services"
	@echo "  make down      - Stop all services"
	@echo "  make restart   - Restart all services"
	@echo "  make logs      - View logs for all services"
	@echo "  make init-db   - Initialize database"
	@echo "  make check-db  - Check database health"
	@echo "  make clean     - Clean up Docker resources"
	@echo ""
	@echo "Development Commands:"
	@echo "  make dev-up    - Start development services"
	@echo "  make dev-down  - Stop development services"
	@echo "  make dev-logs  - View development logs"
	@echo ""
	@echo "Service-specific Commands:"
	@echo "  make logs-db       - View database logs"
	@echo "  make logs-backend  - View backend logs"
	@echo "  make logs-frontend - View frontend logs"
	@echo "  make shell-backend - Access backend shell"
	@echo "  make shell-db      - Access database shell"

# Production commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart: down up

logs:
	docker-compose logs -f

init-db:
	docker-compose exec backend python db/init_db.py --init

check-db:
	docker-compose exec backend python db/init_db.py --check

# Development commands
dev-up:
	docker-compose -f docker-compose.dev.yml up -d

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-init-db:
	docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --init

# Service-specific commands
logs-db:
	docker-compose logs -f db

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

shell-backend:
	docker-compose exec backend bash

shell-db:
	docker-compose exec db psql -U yudai_user -d yudai_db

# Cleanup commands
clean:
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

clean-all:
	docker-compose down -v
	docker system prune -a -f
	docker volume prune -f

# Status commands
status:
	docker-compose ps

health:
	docker-compose ps
	@echo ""
	@echo "Container Health:"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Backup and restore
backup-db:
	docker-compose exec db pg_dump -U yudai_user yudai_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Database backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

restore-db:
	@echo "Usage: make restore-db BACKUP_FILE=backup_file.sql"
	@if [ -z "$(BACKUP_FILE)" ]; then echo "Error: BACKUP_FILE not specified"; exit 1; fi
	docker-compose exec -T db psql -U yudai_user -d yudai_db < $(BACKUP_FILE)

# Quick start
quickstart: build up init-db
	@echo "✓ YudaiV3 is now running!"
	@echo "  Frontend: http://localhost"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

dev-quickstart: dev-up dev-init-db
	@echo "✓ YudaiV3 development environment is now running!"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs" 