#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ROS 接口与公共工具函数

本文件用于放置与 ROS 数据接口相关的通用函数，
避免主脚本里堆太多基础逻辑。
"""

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml_config(config_path: str) -> Dict[str, Any]:
    """
    读取 YAML 配置文件。

    参数:
        config_path: 配置文件路径

    返回:
        dict: 配置内容
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    return data


def ros_stamp_to_sec(stamp) -> float:
    """
    将 ROS2 Header 中的 stamp 转成浮点秒。

    参数:
        stamp: builtin_interfaces.msg.Time 类型对象

    返回:
        float: 秒
    """
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9