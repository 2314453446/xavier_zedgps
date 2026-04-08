#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export ADE_NAME=camera_ros

# 1) 已运行：直接进入 root
if ade status >/dev/null 2>&1; then
  exec ade enter -u root
fi
if docker ps --format '{{.Names}}' | grep -qx "$ADE_NAME"; then
  exec ade enter  -u root
fi

# 2) 已存在但退出：启动“同一个”容器，再以 root 进入
if docker ps -a --format '{{.Names}}' | grep -qx "$ADE_NAME"; then
  docker start "$ADE_NAME" >/dev/null
  exec ade enter -u root
fi

# 3) 容器不存在：第一次创建才 start
ade start
exec ade enter -u root
