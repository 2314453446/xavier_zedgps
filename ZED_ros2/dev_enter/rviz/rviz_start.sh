#!/usr/bin/env bash

# 允许GUI
xhost +local:root

CONTAINER_NAME="rviz_container"
IMAGE_NAME="rviz_arm_humble:latest"

# ===== 1. 如果容器不存在 → 创建 =====
if [ ! "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "[Create container]"
    docker run -dit \
        --net=host \
        --runtime nvidia \
        --name $CONTAINER_NAME \
        -e DISPLAY=$DISPLAY \
        -e FASTDDS_BUILTIN_TRANSPORTS=UDPv4 \
	-e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
	-v /etc/localtime:/etc/localtime:ro \
	-v /etc/timezone:/etc/timezone:ro \
        $IMAGE_NAME \
        tail -f /dev/null
fi

# ===== 2. 启动容器 =====
docker start $CONTAINER_NAME >/dev/null 2>&1

# ===== 3. 进入终端（不启动 RViz）=====
echo "[Enter RViz container]"
docker exec -it $CONTAINER_NAME \
    bash -c "source /opt/ros/humble/setup.bash && bash"
