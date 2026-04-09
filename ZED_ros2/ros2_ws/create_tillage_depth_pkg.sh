#!/usr/bin/env bash
set -euo pipefail

# ========= 可修改参数 =========
PROJECT_DIR="tillage_depth_estimator"
BACKUP_SUFFIX="$(date +%Y%m%d_%H%M%S)"
NEW_PROJECT_NAME="tillage_depth_dev"

# ========= 基础检查 =========
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[ERROR] Project directory not found: $PROJECT_DIR"
    exit 1
fi

echo "========================================"
echo " Restructure project for pure Python dev"
echo "========================================"
echo "Old project dir : $PROJECT_DIR"
echo "New project dir : $NEW_PROJECT_NAME"
echo

# ========= 1. 备份旧目录 =========
BACKUP_DIR="${PROJECT_DIR}_backup_${BACKUP_SUFFIX}"
echo "[1/6] Backing up old project to: $BACKUP_DIR"
cp -r "$PROJECT_DIR" "$BACKUP_DIR"

# ========= 2. 如需改名，复制为新项目目录 =========
if [ "$PROJECT_DIR" != "$NEW_PROJECT_NAME" ]; then
    echo "[2/6] Copying project to new pure-python root: $NEW_PROJECT_NAME"
    rm -rf "$NEW_PROJECT_NAME"
    cp -r "$PROJECT_DIR" "$NEW_PROJECT_NAME"
else
    echo "[2/6] Project name unchanged, restructuring in place."
fi

TARGET_DIR="$NEW_PROJECT_NAME"

# ========= 3. 删除旧的 ROS2 编译相关结构 =========
echo "[3/6] Removing old ROS2 package/build-oriented structure..."

rm -f "${TARGET_DIR}/package.xml" || true
rm -f "${TARGET_DIR}/setup.py" || true
rm -f "${TARGET_DIR}/setup.cfg" || true

rm -rf "${TARGET_DIR}/resource" || true
rm -rf "${TARGET_DIR}/launch" || true
rm -rf "${TARGET_DIR}/test" || true

# ========= 4. 新建新的纯 Python 开发目录 =========
echo "[4/6] Creating new pure-python project structure..."

mkdir -p "${TARGET_DIR}/docs"
mkdir -p "${TARGET_DIR}/config"
mkdir -p "${TARGET_DIR}/scripts"
mkdir -p "${TARGET_DIR}/modules"
mkdir -p "${TARGET_DIR}/data/logs"
mkdir -p "${TARGET_DIR}/data/screenshots"
mkdir -p "${TARGET_DIR}/data/debug_output"

touch "${TARGET_DIR}/modules/__init__.py"
touch "${TARGET_DIR}/README.md"
touch "${TARGET_DIR}/run_in_container.sh"

touch "${TARGET_DIR}/docs/stage1_数据链路开发说明.md"

touch "${TARGET_DIR}/config/topics.yaml"
touch "${TARGET_DIR}/config/board.yaml"
touch "${TARGET_DIR}/config/ground_plane.yaml"
touch "${TARGET_DIR}/config/visualization.yaml"

touch "${TARGET_DIR}/scripts/stage1_data_probe.py"
touch "${TARGET_DIR}/scripts/stage2_board_pose.py"
touch "${TARGET_DIR}/scripts/stage3_tool_point.py"
touch "${TARGET_DIR}/scripts/stage4_ground_plane.py"
touch "${TARGET_DIR}/scripts/stage5_depth_estimator.py"
touch "${TARGET_DIR}/scripts/stage6_rviz_visualizer.py"

touch "${TARGET_DIR}/modules/ros_interfaces.py"
touch "${TARGET_DIR}/modules/board_detector.py"
touch "${TARGET_DIR}/modules/tool_transform.py"
touch "${TARGET_DIR}/modules/ground_plane.py"
touch "${TARGET_DIR}/modules/depth_estimator.py"
touch "${TARGET_DIR}/modules/visualization.py"
touch "${TARGET_DIR}/modules/utils.py"

# ========= 5. 迁移旧 Python 文件 =========
echo "[5/6] Migrating reusable python files from old nested package (if found)..."

OLD_PY_DIR="${TARGET_DIR}/tillage_depth_estimator"

if [ -d "$OLD_PY_DIR" ]; then
    for f in board_detector.py tool_transform.py ground_plane.py depth_estimator.py visualization.py utils.py; do
        if [ -f "${OLD_PY_DIR}/${f}" ]; then
            echo "  - moving ${f} -> modules/${f}"
            mv "${OLD_PY_DIR}/${f}" "${TARGET_DIR}/modules/${f}"
        fi
    done

    if [ -f "${OLD_PY_DIR}/tillage_depth_node.py" ]; then
        echo "  - moving tillage_depth_node.py -> scripts/stage1_data_probe.py (only if target empty)"
        if [ ! -s "${TARGET_DIR}/scripts/stage1_data_probe.py" ]; then
            mv "${OLD_PY_DIR}/tillage_depth_node.py" "${TARGET_DIR}/scripts/stage1_data_probe.py"
        else
            echo "    target already has content, keeping old file in place"
        fi
    fi

    # 删除旧嵌套目录（如果为空）
    find "$OLD_PY_DIR" -type f | grep -q . || rm -rf "$OLD_PY_DIR" || true
fi

# ========= 6. 生成基础 README =========
echo "[6/6] Writing README and run script..."

cat > "${TARGET_DIR}/README.md" << 'EOF'
# tillage_depth_dev

Pure Python development project for tillage depth estimation.

## Development background
- Host machine: conda Python environment for code editing
- ROS environment: inside container
- ZED2i ROS wrapper is published inside container
- No colcon build in current stage
- Run scripts directly with python3 inside ROS container

## Directory overview
- docs/: development documents
- config/: configuration files
- scripts/: stage-wise runnable scripts
- modules/: reusable algorithm modules
- data/: logs, screenshots, debug outputs

## Current development strategy
Stage-by-stage development:
1. Data link validation
2. Calibration board pose estimation
3. Tool reference point transform
4. Ground plane fitting
5. Depth estimation
6. RViz visualization
EOF

cat > "${TARGET_DIR}/run_in_container.sh" << 'EOF'
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
EOF
chmod +x "${TARGET_DIR}/run_in_container.sh"

echo
echo "========================================"
echo " Done."
echo "========================================"
echo "Backup created at : $BACKUP_DIR"
echo "New project dir   : $TARGET_DIR"
echo
echo "New structure:"
find "$TARGET_DIR" -maxdepth 3 | sort