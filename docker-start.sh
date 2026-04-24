#!/usr/bin/env bash
set -e

export DISPLAY=${DISPLAY:-:99}
export ZONES_HOST=${ZONES_HOST:-0.0.0.0}
export ZONES_DASHBOARD_PORT=${ZONES_DASHBOARD_PORT:-8787}
export ZONES_WEBSOCKET_PORT=${ZONES_WEBSOCKET_PORT:-8090}
export ZONES_METRICS_PORT=${ZONES_METRICS_PORT:-9108}

echo "========================================"
echo "Starting ZONES container"
echo "========================================"

echo "Starting virtual display on ${DISPLAY}..."
Xvfb "${DISPLAY}" -screen 0 1280x800x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

sleep 2

echo "Starting Fluxbox window manager..."
fluxbox >/tmp/fluxbox.log 2>&1 &
FLUXBOX_PID=$!

sleep 1

echo "Starting x11vnc..."
x11vnc \
  -display "${DISPLAY}" \
  -forever \
  -shared \
  -nopw \
  -rfbport 5900 \
  >/tmp/x11vnc.log 2>&1 &
X11VNC_PID=$!

sleep 1

echo "Starting noVNC on port 6080..."
websockify \
  --web=/usr/share/novnc \
  6080 \
  localhost:5900 \
  >/tmp/novnc.log 2>&1 &
NOVNC_PID=$!

sleep 1

echo "Preparing MetaTrader 4 MQL4 folders..."
export WINEPREFIX=${WINEPREFIX:-/root/.wine}
export WINEDEBUG=${WINEDEBUG:--all}

wineboot --init >/tmp/wineboot.log 2>&1 || true

MT4_MQL4_DIR="${WINEPREFIX}/drive_c/Program Files/MetaTrader 4/MQL4"

mkdir -p "${MT4_MQL4_DIR}/Experts"
mkdir -p "${MT4_MQL4_DIR}/Include"
mkdir -p "${MT4_MQL4_DIR}/Libraries"
mkdir -p "${MT4_MQL4_DIR}/Files"

if [ -d "/zones/MQL4" ]; then
  echo "Copying MQL4 files into MetaTrader 4 folder..."
  cp -r /zones/MQL4/* "${MT4_MQL4_DIR}/" || true
else
  echo "No /zones/MQL4 folder found. Skipping MQL4 copy."
fi

cd /zones

echo "Finding ZONES entry file..."

if [ -f "ZONES.py" ]; then
  ZONES_ENTRY="ZONES.py"
elif [ -f "zones.py" ]; then
  ZONES_ENTRY="zones.py"
elif [ -f "main.py" ]; then
  ZONES_ENTRY="main.py"
else
  echo "ERROR: Could not find ZONES.py, zones.py, or main.py inside /zones"
  echo "Files found:"
  ls -la /zones
  exit 1
fi

echo "Starting ZONES app using ${ZONES_ENTRY}..."
python "${ZONES_ENTRY}" &
ZONES_PID=$!

sleep 5

echo "Opening ZONES dashboard in browser..."
if command -v chromium >/dev/null 2>&1; then
  chromium \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --window-size=1280,800 \
    "http://127.0.0.1:${ZONES_DASHBOARD_PORT}" \
    >/tmp/chromium.log 2>&1 &
elif command -v chromium-browser >/dev/null 2>&1; then
  chromium-browser \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --window-size=1280,800 \
    "http://127.0.0.1:${ZONES_DASHBOARD_PORT}" \
    >/tmp/chromium.log 2>&1 &
else
  echo "Chromium not found. Browser auto-open skipped."
fi

echo "========================================"
echo "ZONES is ready"
echo "Dashboard: http://localhost:${ZONES_DASHBOARD_PORT}"
echo "noVNC:     http://localhost:6080/vnc.html"
echo "WebSocket: ws://localhost:${ZONES_WEBSOCKET_PORT}"
echo "Metrics:   http://localhost:${ZONES_METRICS_PORT}"
echo "========================================"

cleanup() {
  echo "Stopping ZONES container..."

  kill "${ZONES_PID}" 2>/dev/null || true
  kill "${NOVNC_PID}" 2>/dev/null || true
  kill "${X11VNC_PID}" 2>/dev/null || true
  kill "${FLUXBOX_PID}" 2>/dev/null || true
  kill "${XVFB_PID}" 2>/dev/null || true

  exit 0
}

trap cleanup SIGINT SIGTERM

wait "${ZONES_PID}"