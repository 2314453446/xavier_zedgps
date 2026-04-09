#!/usr/bin/env bash
set -e

if [ $# -lt 1 ]; then
    echo "Usage: ./run_in_container.sh <python_script>"
    echo "Example: ./run_in_container.sh scripts/stage1_data_probe.py"
    exit 1
fi

SCRIPT_PATH="$1"

source /opt/ros/humble/setup.bash
python3 "$SCRIPT_PATH"
