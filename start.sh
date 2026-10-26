#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🏋️  Starting FitBot Full-Stack App..."

# 1. Start FastAPI backend
echo " Starting FastAPI backend on http://127.0.0.1:8000..."
(cd "$ROOT_DIR/backend" && { [ -x .venv/bin/python ] && PY=.venv/bin/python || PY=python; $PY -m alembic upgrade head && $PY -m uvicorn main_v2:app --host 0.0.0.0 --port "${PORT:-8000}" --reload; }) &

BACKEND_PID=$!

# 2. Start Vite frontend
echo " Starting Vite frontend on http://localhost:5173..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Both services are running!"
echo "   - Frontend: http://localhost:5173"
echo "   - Backend API: http://127.0.0.1:8000"
echo "   - API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Trap termination signals to kill both processes gracefully
trap 'echo "🛑 Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; wait $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' SIGINT SIGTERM EXIT

wait
