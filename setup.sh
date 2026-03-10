#!/bin/bash
set -e
echo "KelownaFireGuard — Setup"
echo "================================"
command -v python3 >/dev/null 2>&1 || { echo "Python 3.12+ required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ required"; exit 1; }
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
  echo "Edit .env and add your NASA_FIRMS_KEY"
fi
echo "Setting up backend..."
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -q && cd ..
echo "Backend ready"
echo "Setting up frontend..."
cd frontend && npm install --silent && cd ..
echo "Frontend ready"
echo ""
echo "To start: make dev"
echo "Dashboard: http://localhost:3000"
echo "API Docs:  http://localhost:8000/docs"
