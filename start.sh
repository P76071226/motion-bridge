#!/bin/bash
set -e

echo "Starting Phone Orientation Dashboard..."
echo ""
echo "1. Syncing dependencies..."
uv sync --quiet

echo "2. Starting server..."
echo "   HTTP Dashboard: http://localhost:8080"
echo "   WebSocket Server: ws://localhost:8765"
echo ""
echo "Press Ctrl+C to stop."
echo ""

uv run python server.py
