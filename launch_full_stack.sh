#!/usr/bin/env bash
# Launch the QEMU<->Gazebo bridge and the teleop node together.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BRIDGE_PORT="${SIM_BRIDGE_PORT:-9000}"

cleanup() {
    echo "Stopping full stack..."
    [[ -n "${BRIDGE_PID:-}" ]] && kill "${BRIDGE_PID}" 2>/dev/null || true
    [[ -n "${TELEOP_PID:-}" ]] && kill "${TELEOP_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting bridge node on port ${BRIDGE_PORT}..."
python3 "${SCRIPT_DIR}/bridge_node.py" --port "${BRIDGE_PORT}" &
BRIDGE_PID=$!

sleep 1

echo "Starting teleop node..."
python3 "${SCRIPT_DIR}/teleop_car.py" &
TELEOP_PID=$!

echo "Full stack running (bridge PID ${BRIDGE_PID}, teleop PID ${TELEOP_PID})."
echo "Press Ctrl+C to stop."
wait
