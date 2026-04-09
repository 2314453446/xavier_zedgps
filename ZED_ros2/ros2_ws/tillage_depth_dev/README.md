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
