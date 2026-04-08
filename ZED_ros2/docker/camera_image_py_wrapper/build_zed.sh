#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"
CONTEXT="${REPO_ROOT}"

echo "Please select the architecture:"
echo "1) x86_64"
echo "2) aarch64"
read -p "Enter your choice (1 or 2): " choice

case $choice in
  1)
    echo "ERROR: this ZED Dockerfile is for Jetson/L4T only, x86_64 is not supported."
    exit 1
    ;;
  2)
    ARCH="aarch64"
    ;;
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

DATE=$(date +'%Y%m%d')
TAG_TIME=$(date +'%Y%m%d.%H%M%S')

if git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
else
  GIT_SHA="nogit"
fi

BASE_DOCKERFILE="${REPO_ROOT}/aarch64.zed_sdk.base.dockerfile"
DERIVED_DOCKERFILE="${REPO_ROOT}/l2_zed2_ros_wapper.dockerfile"
ENTRYPOINT_FILE="${REPO_ROOT}/enterpoint.sh"

BASE_TAG_DATE="openzed-env:${ARCH}_zed_sdk_base_${DATE}"
BASE_TAG_STABLE="openzed-env:${ARCH}_zed_sdk_base"

DERIVED_TAG_DATE="openzed-env:${ARCH}_ros2_foxy_zed_${DATE}"
DERIVED_TAG_STABLE="openzed-env:${ARCH}_ros2_foxy_zed_latest"

if [ ! -f "${BASE_DOCKERFILE}" ]; then
  echo "ERROR: ${BASE_DOCKERFILE} not found."
  exit 1
fi

if [ ! -f "${DERIVED_DOCKERFILE}" ]; then
  echo "ERROR: ${DERIVED_DOCKERFILE} not found."
  exit 1
fi

if [ ! -f "${ENTRYPOINT_FILE}" ]; then
  echo "ERROR: ${ENTRYPOINT_FILE} not found."
  exit 1
fi

echo "[1/2] Build ZED SDK base image: ${BASE_TAG_DATE}"
docker build \
  --no-cache \
  -f "${BASE_DOCKERFILE}" \
  -t "${BASE_TAG_DATE}" \
  --label ade_image_commit_sha="${GIT_SHA}" \
  --label ade_image_commit_tag="${TAG_TIME}" \
  "${CONTEXT}"

docker tag "${BASE_TAG_DATE}" "${BASE_TAG_STABLE}"
echo "Base stable tag: ${BASE_TAG_STABLE}"

echo "[2/2] Build ZED ROS2 image: ${DERIVED_TAG_DATE}"
docker build \
  --no-cache \
  -f "${DERIVED_DOCKERFILE}" \
  --build-arg BASE_IMAGE="${BASE_TAG_STABLE}" \
  -t "${DERIVED_TAG_DATE}" \
  --label ade_image_commit_sha="${GIT_SHA}" \
  --label ade_image_commit_tag="${TAG_TIME}" \
  "${CONTEXT}"

docker tag "${DERIVED_TAG_DATE}" "${DERIVED_TAG_STABLE}"
echo "Derived stable tag: ${DERIVED_TAG_STABLE}"

dangling_images=$(docker images -f "dangling=true" -q)
if [ -n "${dangling_images}" ]; then
  docker rmi -f ${dangling_images} || true
fi

echo ""
echo "Docker images built successfully:"
#echo "  - ${BASE_TAG_DATE}"
echo "  - ${BASE_TAG_STABLE}"
#echo "  - ${DERIVED_TAG_DATE}"
echo "  - ${DERIVED_TAG_STABLE}"
