ARG BASE_IMAGE=openzed-env:aarch64_ros2_foxy_zed_latest
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/opt/pyuser

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-setuptools \
    python3-opencv \
    git \
    vim \
    tmux \
    sudo \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 固定的“用户本地安装”目录
RUN mkdir -p /opt/pyuser && chmod -R 755 /opt/pyuser

# 安装常用 Python 依赖到 /opt/pyuser
RUN umask 022 && \
    PYTHONUSERBASE=/opt/pyuser python3 -m pip install --user --upgrade pip setuptools wheel requests && \
    PYTHONUSERBASE=/opt/pyuser python3 -m pip install --user --no-cache-dir \
      cython \
      numpy \
      pyopengl \
      matplotlib \
      pandas \
      scipy \
      pyyaml \
      tqdm \
      ipython

# 下载/安装 ZED Python API 到 /opt/pyuser
RUN umask 022 && \
    mkdir -p /tmp/zed_pyapi && \
    cd /tmp/zed_pyapi && \
    if [ ! -f /usr/local/zed/get_python_api.py ]; then \
      wget -q download.stereolabs.com/zedsdk/pyzed -O /usr/local/zed/get_python_api.py; \
    fi && \
    python3 /usr/local/zed/get_python_api.py && \
    PYTHONUSERBASE=/opt/pyuser python3 -m pip install --user --ignore-installed /tmp/zed_pyapi/pyzed-*.whl && \
    rm -rf /tmp/zed_pyapi

# 修权限，保证运行时动态用户可读
RUN chmod -R a+rX /opt/pyuser && \
    PYTHONPATH=/opt/pyuser/lib/python3.8/site-packages \
    python3 -c "import pyzed.sl as sl; print(sl)"

# 配合你现有 env.sh 自动加载
RUN mkdir -p /opt/l3_python_userlocal && \
    printf '%s\n' \
    'export PYTHONUSERBASE=/opt/pyuser' \
    'export PATH=/opt/pyuser/bin:$PATH' \
    'export PYTHONPATH=/opt/pyuser/lib/python3.8/site-packages${PYTHONPATH:+:$PYTHONPATH}' \
    'export PYTHONDONTWRITEBYTECODE=1' \
    'export PYTHONUNBUFFERED=1' \
    'alias py=python3' \
    > /opt/l3_python_userlocal/.env.sh

WORKDIR /workspace
