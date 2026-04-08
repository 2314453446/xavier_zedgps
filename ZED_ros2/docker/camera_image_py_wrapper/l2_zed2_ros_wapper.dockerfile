# l2_zed2_ros_wapper.dockerfile
# L2: Lightweight ROS 2 Foxy runtime for Python publisher/subscriber nodes
# No zed-ros2-wrapper build

ARG BASE_IMAGE=openzed-env:aarch64_zed_sdk_base
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV ROS_DISTRO=foxy
ENV ROS_WS=/ros2_ws

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ------------------------------------------------------------------------------
# Base tools
# ------------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    curl \
    wget \
    git \
    gnupg2 \
    lsb-release \
    ca-certificates \
    software-properties-common \
    build-essential \
    cmake \
    pkg-config \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-argcomplete \
    bash-completion && \
    locale-gen en_US en_US.UTF-8 && \
    update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# ROS 2 Foxy repository + lightweight runtime
# 不装 wrapper，不编源码，只保留 Python 节点发布/订阅所需环境
# ------------------------------------------------------------------------------
RUN add-apt-repository universe && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | apt-key add - && \
    echo "deb http://packages.ros.org/ros2/ubuntu focal main" > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      python3-rosdep \
      python3-colcon-common-extensions \
      ros-foxy-ros-base \
      ros-foxy-rclpy \
      ros-foxy-rclcpp \
      ros-foxy-std-msgs \
      ros-foxy-sensor-msgs \
      ros-foxy-geometry-msgs \
      ros-foxy-nav-msgs \
      ros-foxy-visualization-msgs \
      ros-foxy-tf2 \
      ros-foxy-tf2-ros \
      ros-foxy-tf2-geometry-msgs \
      ros-foxy-image-transport \
      ros-foxy-image-geometry \
      ros-foxy-cv-bridge \
      ros-foxy-message-filters \
      ros-foxy-diagnostic-msgs \
      ros-foxy-diagnostic-updater \
      ros-foxy-launch \
      ros-foxy-launch-ros \
      ros-foxy-xacro && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Python tools
# ------------------------------------------------------------------------------
RUN python3 -m pip install --no-cache-dir \
      empy==3.3.4 \
      numpy

# 这里保留一个空工作区，供你后续放自己的 Python ROS 节点
WORKDIR ${ROS_WS}
RUN mkdir -p src

# ------------------------------------------------------------------------------
# Auto-source environment
# ------------------------------------------------------------------------------
RUN printf '%s\n' \
'if [ -f "/opt/ros/foxy/setup.bash" ]; then' \
'    source "/opt/ros/foxy/setup.bash"' \
'fi' \
'if [ -f "/ros2_ws/install/setup.bash" ]; then' \
'    source "/ros2_ws/install/setup.bash"' \
'fi' \
'export PATH=/usr/local/zed/bin:$PATH' \
'export LD_LIBRARY_PATH=/usr/local/zed/lib:/usr/local/zed/lib64:$LD_LIBRARY_PATH' \
> /etc/profile.d/ros2_setup.sh

RUN chmod +x /etc/profile.d/ros2_setup.sh && \
    (grep -qxF 'source /etc/profile.d/ros2_setup.sh' /etc/bash.bashrc || \
     echo 'source /etc/profile.d/ros2_setup.sh' >> /etc/bash.bashrc)


ADD 10_nvidia.json /etc/glvnd/egl_vendor.d/10_nvidia.json
RUN chmod 644 /etc/glvnd/egl_vendor.d/10_nvidia.json
ADD nvidia_icd.json /etc/vulkan/icd.d/nvidia_icd.json
RUN chmod 644 /etc/vulkan/icd.d/nvidia_icd.json
ENV NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:+$NVIDIA_DRIVER_CAPABILITIES,}graphics
COPY env.sh /etc/profile.d/ade_env.sh
COPY enterpoint.sh /ade_entrypoint
ENTRYPOINT ["/ade_entrypoint"]
CMD ["/bin/bash", "-c", "trap 'exit 147' TERM; tail -f /dev/null & while wait ${!}; test $? -ge 128; do true; done"]
