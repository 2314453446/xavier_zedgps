#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 3: 犁耙测量点坐标变换模块

功能:
1. 将 Step 2 输出的板位姿 rvec / tvec 转为变换矩阵
2. 根据板坐标系下的固定点 p_B
3. 计算相机坐标系下的犁耙测量点 p_C
"""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class ToolPointResult:
    """
    犁耙测量点解算结果
    """
    success: bool
    point_in_board: Optional[np.ndarray] = None   # (3,)
    point_in_camera: Optional[np.ndarray] = None  # (3,)
    rotation_matrix: Optional[np.ndarray] = None  # (3,3)
    transform_matrix: Optional[np.ndarray] = None # (4,4)
    message: str = ""


def rvec_tvec_to_transform(rvec: np.ndarray, tvec: np.ndarray) -> np.ndarray:
    """
    将 OpenCV 的 rvec / tvec 转成 4x4 齐次变换矩阵 T_C_B

    参数:
        rvec: shape (3,1) 或 (3,)
        tvec: shape (3,1) 或 (3,)

    返回:
        T_C_B: shape (4,4)
    """
    rvec = np.asarray(rvec, dtype=np.float64).reshape(3, 1)
    tvec = np.asarray(tvec, dtype=np.float64).reshape(3, 1)

    rotation_matrix, _ = cv2.Rodrigues(rvec)

    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = rotation_matrix
    T[:3, 3:4] = tvec
    return T


def transform_tool_point(rvec: np.ndarray, tvec: np.ndarray, point_in_board: np.ndarray) -> ToolPointResult:
    """
    根据板位姿和板坐标系下固定点，计算相机坐标系下的点位置

    数学关系:
        p_C = R_C_B * p_B + t_C_B

    参数:
        rvec:
            板相对于相机的旋转向量

        tvec:
            板相对于相机的平移向量

        point_in_board:
            犁耙测量点在板坐标系下的位置 p_B, shape (3,)

    返回:
        ToolPointResult
    """
    try:
        p_B = np.asarray(point_in_board, dtype=np.float64).reshape(3, 1)
        T_C_B = rvec_tvec_to_transform(rvec, tvec)
        R_C_B = T_C_B[:3, :3]
        t_C_B = T_C_B[:3, 3:4]

        p_C = R_C_B @ p_B + t_C_B

        return ToolPointResult(
            success=True,
            point_in_board=p_B.reshape(3),
            point_in_camera=p_C.reshape(3),
            rotation_matrix=R_C_B,
            transform_matrix=T_C_B,
            message="Tool point transformed successfully"
        )

    except Exception as e:
        return ToolPointResult(
            success=False,
            message=f"transform_tool_point failed: {e}"
        )


def project_point_to_image(
    point_3d_camera: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray
) -> np.ndarray:
    """
    将相机坐标系下的3D点投影到图像平面，用于调试显示

    参数:
        point_3d_camera: shape (3,)
        camera_matrix: shape (3,3)
        dist_coeffs: 畸变参数

    返回:
        uv: shape (2,)
    """
    point_3d_camera = np.asarray(point_3d_camera, dtype=np.float64).reshape(1, 1, 3)

    # 因为点已经在相机坐标系下，所以这里相当于“相机自身坐标投影”
    rvec = np.zeros((3, 1), dtype=np.float64)
    tvec = np.zeros((3, 1), dtype=np.float64)

    image_points, _ = cv2.projectPoints(
        point_3d_camera,
        rvec,
        tvec,
        camera_matrix,
        dist_coeffs
    )

    return image_points.reshape(2)