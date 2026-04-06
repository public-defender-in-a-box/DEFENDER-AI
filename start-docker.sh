#!/usr/bin/env bash
#
# DEFENDER AI — Docker Launcher (macOS / Linux)
# Double-click or run: ./start-docker.sh
#

set -e
cd "$(dirname "$0")"

echo ""
echo "  DEFENDER AI — Starting with Docker..."
echo ""

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker is not installed."
  echo "Download Docker Desktop from https://www.docker.com/products/docker-desktop/"
  exit 1
fi

docker compose up --build -d

echo ""
echo "  DEFENDER AI is running!"
echo "  Open http://localhost:3000 in your browser."
echo ""

# Open browser
sleep 3
if command -v open &>/dev/null; then
  open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:3000"
fi

echo "  To stop: run 'docker compose down' or close Docker Desktop."
echo ""
