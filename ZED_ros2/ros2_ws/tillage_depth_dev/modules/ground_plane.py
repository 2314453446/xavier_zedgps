#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 4: 基于 RGB 像素 ROI 的地面平面拟合模块

功能:
1. 从 organized PointCloud2 还原 HxWx3 点云
2. 按图像像素矩形 ROI 选取对应 3D 点
3. 过滤无效点 / 深度异常点
4. RANSAC 拟合地面平面
5. 最小二乘精修平面
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import numpy as np
from sensor_msgs_py import point_cloud2


@dataclass
class GroundPlaneResult:
    success: bool
    plane: Optional[np.ndarray] = None          # [a,b,c,d]
    normal: Optional[np.ndarray] = None         # [a,b,c]
    roi_points: Optional[np.ndarray] = None     # (N,3)
    inlier_points: Optional[np.ndarray] = None  # (M,3)
    inlier_indices: Optional[np.ndarray] = None
    frame_id: str = ""
    message: str = ""


def organized_pointcloud2_to_xyz_image(msg) -> np.ndarray:
    """
    将 organized PointCloud2 转成 HxWx3 的 xyz 图像。

    兼容 read_points 返回结构化数组(dtype names: x,y,z) 的情况。
    """
    h = msg.height
    w = msg.width

    if h <= 1 or w <= 1:
        raise ValueError("PointCloud2 is not organized. width/height layout is not image-like.")

    points = point_cloud2.read_points(
        msg,
        field_names=("x", "y", "z"),
        skip_nans=False
    )

    # 转成 numpy 数组
    arr = np.asarray(points)

    # 情况1：结构化数组，字段名为 x/y/z
    if arr.dtype.names is not None:
        if not all(name in arr.dtype.names for name in ("x", "y", "z")):
            raise ValueError(f"Structured point cloud fields do not contain x/y/z: {arr.dtype.names}")

        x = arr["x"].astype(np.float64)
        y = arr["y"].astype(np.float64)
        z = arr["z"].astype(np.float64)

        if x.size != h * w:
            raise ValueError(
                f"Point count mismatch: got {x.size}, expected {h*w}. "
                "Cannot reshape into organized xyz image."
            )

        xyz = np.stack([x, y, z], axis=-1).reshape(h, w, 3)
        return xyz

    # 情况2：普通 Nx3 数组
    arr = np.asarray(arr, dtype=np.float64)

    if arr.ndim != 2 or arr.shape[1] < 3:
        raise ValueError(f"Unexpected point cloud array shape: {arr.shape}")

    if arr.shape[0] != h * w:
        raise ValueError(
            f"Point count mismatch: got {arr.shape[0]}, expected {h*w}. "
            "Cannot reshape into organized xyz image."
        )

    xyz = arr[:, :3].reshape(h, w, 3)
    return xyz


def extract_points_from_pixel_roi(xyz_image: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """
    从 HxWx3 点云图像中，按像素 ROI 取出对应 3D 点。
    """
    gcfg = cfg.get("ground", {})

    h, w, _ = xyz_image.shape

    u_min = int(gcfg.get("u_min", 0))
    u_max = int(gcfg.get("u_max", w - 1))
    v_min = int(gcfg.get("v_min", 0))
    v_max = int(gcfg.get("v_max", h - 1))

    u_min = max(0, min(u_min, w - 1))
    u_max = max(0, min(u_max, w - 1))
    v_min = max(0, min(v_min, h - 1))
    v_max = max(0, min(v_max, h - 1))

    if u_max < u_min or v_max < v_min:
        return np.empty((0, 3), dtype=np.float64)

    roi_xyz = xyz_image[v_min:v_max + 1, u_min:u_max + 1, :]
    points = roi_xyz.reshape(-1, 3)
    return points

def orient_plane_normal_toward_camera(plane: np.ndarray, reference_points: np.ndarray) -> np.ndarray:
    """
    约束平面法向朝向相机原点。

    参数:
        plane: [a,b,c,d]
        reference_points: 用于估计平面中心的一组点，通常取平面内点

    返回:
        plane_oriented: 方向约束后的平面参数
    """
    if plane is None or reference_points is None or len(reference_points) == 0:
        return plane

    center = np.mean(reference_points, axis=0)
    normal = plane[:3]

    # 若法向与“从相机到平面中心”的向量同向，则翻转，
    # 使法向朝向相机
    if np.dot(normal, center) > 0:
        plane = -plane

    return plane

def filter_valid_points(points: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """
    过滤:
    1. 非有限值点
    2. 距离范围外点

    注意：
    这里不用单独某个坐标轴分量做“深度”过滤，
    而是用 3D 欧氏距离，避免因 frame 定义不同误删有效点。
    """
    if points.size == 0:
        return points

    gcfg = cfg.get("ground", {})
    depth_min = float(gcfg.get("depth_min_m", 0.2))
    depth_max = float(gcfg.get("depth_max_m", 3.0))

    finite_mask = np.isfinite(points).all(axis=1)
    points = points[finite_mask]

    if len(points) == 0:
        return points

    depth = np.linalg.norm(points, axis=1)
    depth_mask = (depth >= depth_min) & (depth <= depth_max)

    return points[depth_mask]


def sample_points(points: np.ndarray, max_points: int, seed: int = 42) -> np.ndarray:
    """
    如果点数太多，随机采样。
    """
    if len(points) <= max_points:
        return points

    rng = np.random.default_rng(seed)
    ids = rng.choice(len(points), size=max_points, replace=False)
    return points[ids]


def fit_plane_from_3_points(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> Optional[np.ndarray]:
    """
    用三点求平面 ax+by+cz+d=0，返回单位法向的平面参数。
    """
    v1 = p2 - p1
    v2 = p3 - p1
    normal = np.cross(v1, v2)
    norm = np.linalg.norm(normal)

    if norm < 1e-9:
        return None

    normal = normal / norm
    d = -np.dot(normal, p1)
    return np.array([normal[0], normal[1], normal[2], d], dtype=np.float64)


def point_to_plane_distances(points: np.ndarray, plane: np.ndarray) -> np.ndarray:
    """
    计算点到平面的绝对距离。
    plane: [a,b,c,d]，且法向已归一化
    """
    return np.abs(points @ plane[:3] + plane[3])


def ransac_fit_plane(points: np.ndarray, threshold: float, max_iterations: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    RANSAC 拟合平面。
    返回:
        best_plane
        best_inlier_indices
    """
    n = len(points)
    if n < 3:
        return None, None

    rng = np.random.default_rng(42)

    best_plane = None
    best_inlier_indices = None
    best_count = 0

    for _ in range(max_iterations):
        ids = rng.choice(n, size=3, replace=False)
        plane = fit_plane_from_3_points(points[ids[0]], points[ids[1]], points[ids[2]])
        if plane is None:
            continue

        distances = point_to_plane_distances(points, plane)
        inlier_indices = np.where(distances < threshold)[0]
        count = len(inlier_indices)

        if count > best_count:
            best_count = count
            best_plane = plane
            best_inlier_indices = inlier_indices

    return best_plane, best_inlier_indices


def refine_plane_least_squares(points: np.ndarray) -> Optional[np.ndarray]:
    """
    用内点做最小二乘平面精修。
    """
    if len(points) < 3:
        return None

    centroid = points.mean(axis=0)
    centered = points - centroid

    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    norm = np.linalg.norm(normal)

    if norm < 1e-9:
        return None

    normal = normal / norm
    d = -np.dot(normal, centroid)
    return np.array([normal[0], normal[1], normal[2], d], dtype=np.float64)


def fit_ground_plane_from_pixel_roi(xyz_image: np.ndarray, cfg: Dict[str, Any], frame_id: str = "") -> GroundPlaneResult:
    """
    完整流程:
    1. 按像素 ROI 取点
    2. 过滤无效点
    3. 采样
    4. RANSAC 拟合
    5. 最小二乘精修
    """
    roi_points = extract_points_from_pixel_roi(xyz_image, cfg)
    if len(roi_points) == 0:
        return GroundPlaneResult(success=False, frame_id=frame_id, message="Pixel ROI is empty")

    valid_points = filter_valid_points(roi_points, cfg)
    if len(valid_points) < 3:
        return GroundPlaneResult(
            success=False,
            roi_points=roi_points,
            frame_id=frame_id,
            message="Valid ROI points too few after filtering"
        )

    gcfg = cfg.get("ground", {})
    threshold = float(gcfg.get("ransac_threshold_m", 0.02))
    max_iterations = int(gcfg.get("ransac_max_iterations", 300))
    min_inliers = int(gcfg.get("min_inliers", 500))
    max_points = int(gcfg.get("max_points_for_ransac", 20000))

    sampled_points = sample_points(valid_points, max_points=max_points)

    init_plane, inlier_indices = ransac_fit_plane(
        sampled_points,
        threshold=threshold,
        max_iterations=max_iterations
    )

    if init_plane is None or inlier_indices is None:
        return GroundPlaneResult(
            success=False,
            roi_points=valid_points,
            frame_id=frame_id,
            message="RANSAC failed"
        )

    inlier_points = sampled_points[inlier_indices]
    if len(inlier_points) < min_inliers:
        return GroundPlaneResult(
            success=False,
            roi_points=valid_points,
            inlier_points=inlier_points,
            frame_id=frame_id,
            message=f"Too few inliers: {len(inlier_points)} < {min_inliers}"
        )

    refined_plane = refine_plane_least_squares(inlier_points)
    if refined_plane is None:
        return GroundPlaneResult(
            success=False,
            roi_points=valid_points,
            inlier_points=inlier_points,
            frame_id=frame_id,
            message="Plane refinement failed"
        )

    # 约束法向朝向相机
    refined_plane = orient_plane_normal_toward_camera(refined_plane, inlier_points)
    normal = refined_plane[:3]

    return GroundPlaneResult(
        success=True,
        plane=refined_plane,
        normal=normal,
        roi_points=valid_points,
        inlier_points=inlier_points,
        inlier_indices=inlier_indices,
        frame_id=frame_id,
        message="Ground plane fitted successfully"
    )