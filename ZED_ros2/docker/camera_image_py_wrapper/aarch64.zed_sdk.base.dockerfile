# aarch64.zed_sdk.base.dockerfile
# JP5.1.2 / L4T 35.4.1
# Base: ZED SDK 5.2 + ZED Python API

ARG L4T_BASE_IMAGE=l4t-jetpack
ARG L4T_MAJOR_VERSION=35
ARG L4T_MINOR_VERSION=4
ARG L4T_PATCH_VERSION=1

ARG ZED_SDK_MAJOR=5
ARG ZED_SDK_MINOR=2

FROM nvcr.io/nvidia/${L4T_BASE_IMAGE}:r${L4T_MAJOR_VERSION}.${L4T_MINOR_VERSION}.${L4T_PATCH_VERSION}

ARG L4T_MAJOR_VERSION
ARG L4T_MINOR_VERSION
ARG L4T_PATCH_VERSION
ARG ZED_SDK_MAJOR
ARG ZED_SDK_MINOR

ENV LOGNAME=root
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update -y && \
    apt-get install --no-install-recommends -y \
      apt-utils \
      dialog \
      tzdata \
      locales \
      lsb-release \
      wget \
      curl \
      less \
      zstd \
      udev \
      sudo \
      git \
      ca-certificates \
      apt-transport-https \
      gnupg2 \
      software-properties-common \
      file \
      python3 \
      python3-pip \
      python3-dev \
      python3-setuptools \
      build-essential \
      cmake \
      pkg-config \
      nano \
      bash-completion && \
    locale-gen en_US en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 && \
    ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && \
    echo ${TZ} > /etc/timezone && \
    echo "# R${L4T_MAJOR_VERSION} (release), REVISION: ${L4T_MINOR_VERSION}.${L4T_PATCH_VERSION}" > /etc/nv_tegra_release && \
    rm -rf /var/lib/apt/lists/*

RUN which file && file --version && which zstd

RUN wget -q --no-check-certificate \
      -O /tmp/ZED_SDK_Linux.run \
      https://download.stereolabs.com/zedsdk/${ZED_SDK_MAJOR}.${ZED_SDK_MINOR}/l4t${L4T_MAJOR_VERSION}.${L4T_MINOR_VERSION}/jetsons && \
    chmod +x /tmp/ZED_SDK_Linux.run && \
    /tmp/ZED_SDK_Linux.run silent skip_tools skip_drivers && \
    rm -rf /usr/local/zed/resources/* && \
    rm -f /tmp/ZED_SDK_Linux.run

# 只补最少 Python 依赖，避免破坏系统 Python 环境
RUN python3 -m pip install --no-cache-dir pyopengl

RUN ln -sf /usr/lib/aarch64-linux-gnu/tegra/libv4l2.so.0 /usr/lib/aarch64-linux-gnu/libv4l2.so

ENV PATH=/usr/local/zed/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/zed/lib:/usr/local/zed/lib64:${LD_LIBRARY_PATH}

WORKDIR /usr/local/zed
