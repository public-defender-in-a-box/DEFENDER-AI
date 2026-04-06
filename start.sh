#!/usr/bin/env bash
#
# DEFENDER AI — One-Click Launcher (macOS / Linux)
#
# Double-click this file (or run ./start.sh) to start the application.
# It will install dependencies, start the backend and frontend, and
# open the app in your default browser.
#
# Prerequisites:
#   - Node.js 18+ (https://nodejs.org)
#   - Python 3.11+ (https://python.org)
#
# To stop: close this terminal window, or press Ctrl+C.
#

set -e

# ---------- Resolve project root ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Colors ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      DEFENDER AI — Starting Up...        ║${NC}"
echo -e "${BLUE}║   Public Defender AI Assistant            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ---------- Check prerequisites ----------
check_command() {
  if ! command -v "$1" &>/dev/null; then
    echo -e "${RED}ERROR: $1 is not installed.${NC}"
    echo "Please install $1 and try again."
    echo "  $2"
    exit 1
  fi
}

check_command node "Download from https://nodejs.org (version 18 or later)"
check_command npm  "Comes with Node.js — download from https://nodejs.org"
check_command python3 "Download from https://python.org (version 3.11 or later)"

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
  echo -e "${RED}ERROR: Node.js 18+ required (found v$(node -v)).${NC}"
  exit 1
fi

echo -e "${GREEN}✓${NC} Node.js $(node -v)"
echo -e "${GREEN}✓${NC} Python $(python3 --version | awk '{print $2}')"
echo ""

# ---------- Install frontend dependencies ----------
echo -e "${YELLOW}Installing frontend dependencies...${NC}"
cd "$SCRIPT_DIR/packages/web"
if [ ! -d node_modules ]; then
  npm install --no-audit --no-fund 2>&1 | tail -1
else
  echo "  (node_modules exists, skipping — run 'npm install' manually to update)"
fi

# ---------- Set up Python virtual environment ----------
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd "$SCRIPT_DIR/packages/api"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt 2>&1 | tail -1

# ---------- Ensure .env.local exists for frontend ----------
cd "$SCRIPT_DIR/packages/web"
if [ ! -f .env.local ]; then
  cat > .env.local <<'ENVEOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_SECRET=defender-ai-dev-secret-change-in-production
NEXTAUTH_URL=http://localhost:3000
ENVEOF
  echo -e "${GREEN}✓${NC} Created .env.local with defaults"
fi

# ---------- Start backend ----------
echo ""
echo -e "${BLUE}Starting backend (FastAPI) on http://localhost:8000 ...${NC}"
cd "$SCRIPT_DIR/packages/api"
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ---------- Start frontend ----------
echo -e "${BLUE}Starting frontend (Next.js) on http://localhost:3000 ...${NC}"
cd "$SCRIPT_DIR/packages/web"
npm run dev &
FRONTEND_PID=$!

# ---------- Cleanup on exit ----------
cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down DEFENDER AI...${NC}"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID 2>/dev/null || true
  wait $FRONTEND_PID 2>/dev/null || true
  echo -e "${GREEN}Done. Goodbye.${NC}"
}
trap cleanup EXIT INT TERM

# ---------- Wait for frontend, then open browser ----------
echo ""
echo -e "${YELLOW}Waiting for servers to start...${NC}"
sleep 4

# Open browser
if command -v open &>/dev/null; then
  open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:3000"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  DEFENDER AI is running!                 ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║  Frontend:  http://localhost:3000         ║${NC}"
echo -e "${GREEN}║  Backend:   http://localhost:8000         ║${NC}"
echo -e "${GREEN}║                                          ║${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop.                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# Keep script alive
wait
