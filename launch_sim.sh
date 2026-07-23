#!/usr/bin/env bash
# Launch the Gazebo maze simulation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make the local car model discoverable by Gazebo.
export GZ_SIM_RESOURCE_PATH="${SCRIPT_DIR}/models:${GZ_SIM_RESOURCE_PATH:-}"
export IGN_GAZEBO_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH}"

WORLD="${SCRIPT_DIR}/worlds/maze.sdf"

if command -v gz >/dev/null 2>&1; then
    echo "Launching Gazebo (gz sim) with ${WORLD}"
    exec gz sim -r "${WORLD}"
elif command -v ign >/dev/null 2>&1; then
    echo "Launching Ignition Gazebo with ${WORLD}"
    exec ign gazebo -r "${WORLD}"
else
    echo "Error: neither 'gz' nor 'ign' found. Install Gazebo (Garden/Harmonic)." >&2
    exit 1
fi
