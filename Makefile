.PHONY: help dev backend frontend docker clean test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start both backend and frontend in dev mode
	@echo "Starting backend..."
	cd backend && uvicorn main:app --reload --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev &

backend: ## Start backend only
	cd backend && uvicorn main:app --reload --port 8000

frontend: ## Start frontend only
	cd frontend && npm run dev

docker: ## Start with Docker Compose
	docker-compose up --build

docker-down: ## Stop Docker containers
	docker-compose down

setup: ## Initial project setup
	cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

db-reset: ## Reset database
	rm -f backend/fireguard.db

test-nlp: ## Test NLP engine
	cd backend && python -c "from services.nlp_engine import NLPEngine; nlp = NLPEngine(); texts = ['Huge fire on Knox Mountain, smoke everywhere!', 'Nice day at the beach', 'EVACUATE NOW - flames approaching Lakeshore Rd', 'Going to buy firewood for campfire']; [print(f'{s:.2f} | {t[:60]}') for t in texts for s,k,_ in [nlp.analyze_text(t)]]"

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -f backend/fireguard.db
