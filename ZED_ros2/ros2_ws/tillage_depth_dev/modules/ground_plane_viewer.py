#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 4 局部点云与拟合平面调试可视化

使用 matplotlib 3D 窗口显示：
1. ROI 局部点云
2. RANSAC 内点
3. 拟合平面面片
4. 平面法向箭头
"""

from typing import Optional

import numpy as np
import matplotlib.pyplot as plt


class GroundPlaneDebugViewer:
    def __init__(self, plane_extent: float = 0.5, max_draw_points: int = 3000):
        """
        参数:
            plane_extent:
                平面面片显示尺寸的一半，单位米

            max_draw_points:
                每次最多绘制多少个点，避免窗口太卡
        """
        self.plane_extent = float(plane_extent)
        self.max_draw_points = int(max_draw_points)

        plt.ion()
        self.fig = plt.figure("Stage4 Ground Plane Debug")
        self.ax = self.fig.add_subplot(111, projection="3d")

    def update(
        self,
        roi_points: Optional[np.ndarray],
        inlier_points: Optional[np.ndarray],
        plane: Optional[np.ndarray],
        normal: Optional[np.ndarray],
    ):
        """
        更新调试窗口内容。
        """
        self.ax.cla()

        if roi_points is not None and len(roi_points) > 0:
            pts = self._sample_points(roi_points, self.max_draw_points)
            self.ax.scatter(
                pts[:, 0], pts[:, 1], pts[:, 2],
                s=1, alpha=0.15, label="ROI points"
            )

        if inlier_points is not None and len(inlier_points) > 0:
            pts = self._sample_points(inlier_points, self.max_draw_points)
            self.ax.scatter(
                pts[:, 0], pts[:, 1], pts[:, 2],
                s=3, alpha=0.7, label="Plane inliers"
            )

        if plane is not None and normal is not None and inlier_points is not None and len(inlier_points) > 10:
            center = np.mean(inlier_points, axis=0)
            self._draw_plane_patch(plane, center)
            self._draw_normal_arrow(center, normal)

        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")
        self.ax.set_title("Local Point Cloud + RANSAC Plane")
        self.ax.legend(loc="upper right")

        self._set_axes_equal_from_points(roi_points, inlier_points)
        plt.tight_layout()
        plt.draw()
        plt.pause(0.001)

    def _draw_plane_patch(self, plane: np.ndarray, center: np.ndarray):
        """
        在拟合平面上画一个局部矩形面片。
        """
        normal = plane[:3]
        normal = normal / (np.linalg.norm(normal) + 1e-12)

        # 构造平面内两个正交基向量
        ref = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        if abs(np.dot(ref, normal)) > 0.9:
            ref = np.array([0.0, 1.0, 0.0], dtype=np.float64)

        u = np.cross(normal, ref)
        u = u / (np.linalg.norm(u) + 1e-12)

        v = np.cross(normal, u)
        v = v / (np.linalg.norm(v) + 1e-12)

        e = self.plane_extent

        corners = np.array([
            center + (-e) * u + (-e) * v,
            center + ( e) * u + (-e) * v,
            center + ( e) * u + ( e) * v,
            center + (-e) * u + ( e) * v,
        ])

        x = corners[:, 0].reshape(2, 2)
        y = corners[:, 1].reshape(2, 2)
        z = corners[:, 2].reshape(2, 2)

        # 重新排成 surface 所需形状
        x = np.array([[corners[0, 0], corners[1, 0]],
                      [corners[3, 0], corners[2, 0]]])
        y = np.array([[corners[0, 1], corners[1, 1]],
                      [corners[3, 1], corners[2, 1]]])
        z = np.array([[corners[0, 2], corners[1, 2]],
                      [corners[3, 2], corners[2, 2]]])

        self.ax.plot_surface(x, y, z, alpha=0.35)

    def _draw_normal_arrow(self, center: np.ndarray, normal: np.ndarray):
        """
        画平面法向箭头。
        """
        n = normal / (np.linalg.norm(normal) + 1e-12)
        arrow_len = self.plane_extent * 0.8

        self.ax.quiver(
            center[0], center[1], center[2],
            n[0], n[1], n[2],
            length=arrow_len,
            normalize=True
        )

    @staticmethod
    def _sample_points(points: np.ndarray, max_points: int) -> np.ndarray:
        if points is None or len(points) <= max_points:
            return points
        rng = np.random.default_rng(42)
        ids = rng.choice(len(points), size=max_points, replace=False)
        return points[ids]

    def _set_axes_equal_from_points(self, roi_points: Optional[np.ndarray], inlier_points: Optional[np.ndarray]):
        """
        让 3D 三轴尺度尽量一致。
        """
        all_pts = []
        if roi_points is not None and len(roi_points) > 0:
            all_pts.append(self._sample_points(roi_points, 1000))
        if inlier_points is not None and len(inlier_points) > 0:
            all_pts.append(self._sample_points(inlier_points, 1000))

        if not all_pts:
            return

        pts = np.vstack(all_pts)
        mins = pts.min(axis=0)
        maxs = pts.max(axis=0)
        center = (mins + maxs) / 2.0
        extent = np.max(maxs - mins) / 2.0
        extent = max(extent, 0.2)

        self.ax.set_xlim(center[0] - extent, center[0] + extent)
        self.ax.set_ylim(center[1] - extent, center[1] + extent)
        self.ax.set_zlim(center[2] - extent, center[2] + extent)