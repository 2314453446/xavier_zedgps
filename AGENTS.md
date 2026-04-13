# AGENTS

## Scope
- This repository contains ZED camera development assets and a ROS2-based tillage depth estimation project.
- The main active project is `ZED_ros2/ros2_ws/tillage_depth_dev`.

## Working Area
- Prefer making changes inside `ZED_ros2/ros2_ws/tillage_depth_dev` unless the task explicitly targets Docker, `third_party`, or the separate `ZED_PY` tree.
- Treat `third_party/`, `ZED_ros2/third_party/`, and `ZED_PY/third_party/` as vendored code. Do not modify them unless the task explicitly requires it.

## Project Layout
- `ZED_ros2/ros2_ws/tillage_depth_dev/config`: YAML configuration for topics, board pose, tool geometry, ground plane, depth, and visualization.
- `ZED_ros2/ros2_ws/tillage_depth_dev/modules`: reusable Python modules for ROS interfaces, board detection, tool transforms, ground fitting, depth estimation, and visualization.
- `ZED_ros2/ros2_ws/tillage_depth_dev/scripts`: stage-by-stage runnable entrypoints.
- `ZED_ros2/ros2_ws/tillage_depth_dev/docs`: development notes and stage documents.
- `ZED_ros2/ros2_ws/tillage_depth_dev/run_in_container.sh`: expected entry script for container-side execution.

## Execution Model
- Current workflow is Python-first, not package-build-first.
- Run scripts directly with `python3` inside the ROS container.
- Do not assume `colcon build` is part of the normal dev loop for `tillage_depth_dev`.

## Common Entry Points
- `scripts/stage1_data_probe.py`
- `scripts/stage2_board_pose.py`
- `scripts/stage3_tool_point.py`
- `scripts/stage4_ground_plane.py`
- `scripts/stage5_depth_estimator.py`
- `scripts/stage6_rviz_visualizer.py`

## Guardrails
- Check current `git status` before editing because this repo is often dirty.
- Avoid broad formatting or tree-wide refactors.
- Preserve existing YAML field names and script/module boundaries unless the task requires a structural change.
- Keep comments concise and only where the logic is not obvious.

## Validation
- Prefer targeted validation close to the edited area.
- For Python changes, run the smallest relevant script or syntax check first.
- If validation depends on ROS topics, container runtime, ZED hardware, or RViz, state clearly what could not be verified locally.
