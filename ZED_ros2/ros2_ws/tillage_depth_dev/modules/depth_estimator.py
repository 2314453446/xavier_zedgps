#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 5: 深度计算模块

功能:
1. 将 optical frame 下的点转换到 camera frame
2. 计算点到平面的有符号距离
3. 按规则输出耕作深度 depth
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np


@dataclass
class DepthResult:
    success: bool
    point_optical: Optional[np.ndarray] = None   # (3,)
    point_camera: Optional[np.ndarray] = None    # (3,)
    plane: Optional[np.ndarray] = None           # (4,)
    signed_dist: Optional[float] = None
    depth: Optional[float] = None
    message: str = ""


def optical_to_camera_frame(point_optical: np.ndarray) -> np.ndarray:
    """
    将 ROS optical frame 下的点转换到普通相机 frame。

    optical frame 约定:
        x_right, y_down, z_forward

    camera frame（ROS body-style camera）约定:
        x_forward, y_left, z_up

    转换关系:
        x_cam = z_opt
        y_cam = -x_opt
        z_cam = -y_opt
    """
    p = np.asarray(point_optical, dtype=np.float64).reshape(3)

    x_opt, y_opt, z_opt = p
    x_cam = z_opt
    y_cam = -x_opt
    z_cam = -y_opt

    return np.array([x_cam, y_cam, z_cam], dtype=np.float64)


def signed_distance_point_to_plane(point: np.ndarray, plane: np.ndarray) -> float:
    """
    计算点到平面的有符号距离。

    要求 plane[:3] 已归一化或近似归一化。
    """
    p = np.asarray(point, dtype=np.float64).reshape(3)
    plane = np.asarray(plane, dtype=np.float64).reshape(4)

    return float(np.dot(plane[:3], p) + plane[3])


def compute_depth(
    point_optical: np.ndarray,
    plane_camera: np.ndarray,
    cfg: Dict[str, Any]
) -> DepthResult:
    """
    完整深度计算流程：
    1. optical -> camera
    2. signed distance
    3. depth according to configured sign rule
    """
    try:
        point_optical = np.asarray(point_optical, dtype=np.float64).reshape(3)
        plane_camera = np.asarray(plane_camera, dtype=np.float64).reshape(4)

        point_camera = optical_to_camera_frame(point_optical)
        signed_dist = signed_distance_point_to_plane(point_camera, plane_camera)

        dcfg = cfg.get("depth", {})
        clamp_negative_to_zero = bool(dcfg.get("clamp_negative_to_zero", True))
        use_negative_signed_as_penetration = bool(
            dcfg.get("use_negative_signed_as_penetration", True)
        )

        if use_negative_signed_as_penetration:
            raw_depth = -signed_dist
        else:
            raw_depth = signed_dist

        if clamp_negative_to_zero:
            depth = max(0.0, raw_depth)
        else:
            depth = raw_depth

        return DepthResult(
            success=True,
            point_optical=point_optical,
            point_camera=point_camera,
            plane=plane_camera,
            signed_dist=signed_dist,
            depth=float(depth),
            message="Depth computed successfully"
        )

    except Exception as e:
        return DepthResult(
            success=False,
            message=f"compute_depth failed: {e}"
        )


class ExponentialSmoother:
    """
    一阶低通滤波器
    """
    def __init__(self, alpha: float = 0.3):
        self.alpha = float(alpha)
        self.value = None

    def update(self, x: float) -> float:
        x = float(x)
        if self.value is None:
            self.value = x
        else:
            self.value = self.alpha * x + (1.0 - self.alpha) * self.value
        return self.value