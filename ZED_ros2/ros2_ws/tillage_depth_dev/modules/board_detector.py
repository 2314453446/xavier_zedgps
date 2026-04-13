#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 2: 标定板检测模块

当前版本目标：
1. 检测单个 AprilTag
2. 提取 4 个角点
3. 结合 CameraInfo 做位姿估计
4. 输出 rvec / tvec
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

import cv2
import numpy as np

try:
    import apriltag
except ImportError:
    apriltag = None


@dataclass
class BoardPoseResult:
    """
    单次检测结果。

    detected:
        是否成功检测到标签并求解位姿

    tag_id:
        标签 ID

    family:
        标签 family

    corners_px:
        图像中的四个角点坐标，shape = (4, 2)

    rvec / tvec:
        OpenCV solvePnP 输出的旋转向量和平移向量
        它们共同描述 T_C_B
    """
    detected: bool
    tag_id: Optional[int] = None
    family: Optional[str] = None
    corners_px: Optional[np.ndarray] = None
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    debug_image: Optional[np.ndarray] = None
    message: str = ""


class AprilTagBoardDetector:
    """
    单标签 AprilTag 检测器。

    第一版设计原则：
    - 只处理一个标签
    - 只处理一个 family
    - 检测到多个时，优先选择面积最大的那个
    """

    def __init__(self, cfg: Dict[str, Any]):
        board_cfg = cfg.get("board", {})

        self.family = board_cfg.get("family", "tag36h11")
        self.tag_size_m = float(board_cfg.get("tag_size_m", 0.16))
        self.debug_draw = bool(board_cfg.get("debug_draw", True))

        if apriltag is None:
            raise ImportError(
                "apriltag package not found. Please install it first, e.g. pip install apriltag"
            )

        options = apriltag.DetectorOptions(families=self.family)
        self.detector = apriltag.Detector(options)

    def detect(
        self,
        image_bgr: np.ndarray,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray
    ) -> BoardPoseResult:
        """
        检测 AprilTag 并估计位姿。

        参数:
            image_bgr:
                OpenCV BGR 图像

            camera_matrix:
                3x3 相机内参矩阵

            dist_coeffs:
                畸变参数

        返回:
            BoardPoseResult
        """
        if image_bgr is None:
            return BoardPoseResult(
                detected=False,
                message="Input image is None"
            )

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detect(gray)

        debug_image = image_bgr.copy() if self.debug_draw else None

        if len(detections) == 0:
            return BoardPoseResult(
                detected=False,
                debug_image=debug_image,
                message="No AprilTag detected"
            )

        # 第一版策略：如果检测到多个，只取图像中面积最大的一个
        best_det = max(detections, key=lambda d: self._quad_area(np.array(d.corners, dtype=np.float32)))
        corners_raw = np.array(best_det.corners, dtype=np.float32)
        corners = self._order_corners_clockwise(corners_raw)
        tag_id = int(best_det.tag_id)

        half = self.tag_size_m / 2.0
        object_points = np.array([
            [-half, -half, 0.0],  # 左上
            [half, -half, 0.0],  # 右上
            [half, half, 0.0],  # 右下
            [-half, half, 0.0],  # 左下
        ], dtype=np.float32)

        success, rvec, tvec = cv2.solvePnP(
            object_points,
            corners,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return BoardPoseResult(
                detected=False,
                tag_id=tag_id,
                family=self.family,
                corners_px=corners,
                debug_image=debug_image,
                message="solvePnP failed"
            )

        if self.debug_draw and debug_image is not None:
            self._draw_debug(
                image=debug_image,
                corners=corners,
                tag_id=tag_id,
                rvec=rvec,
                tvec=tvec,
                camera_matrix=camera_matrix,
                dist_coeffs=dist_coeffs
            )

        return BoardPoseResult(
            detected=True,
            tag_id=tag_id,
            family=self.family,
            corners_px=corners,
            rvec=rvec,
            tvec=tvec,
            debug_image=debug_image,
            message="Detection success"
        )

    @staticmethod
    def _quad_area(corners: np.ndarray) -> float:
        """
        计算四边形面积，用于从多个检测结果中选“最大”的标签。
        """
        return float(cv2.contourArea(corners.reshape(-1, 1, 2)))

    @staticmethod
    def _order_corners_clockwise(corners: np.ndarray) -> np.ndarray:
        pts = corners.astype(np.float32)

        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1).reshape(-1)

        top_left = pts[np.argmin(s)]
        bottom_right = pts[np.argmax(s)]
        top_right = pts[np.argmin(diff)]
        bottom_left = pts[np.argmax(diff)]

        return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)

    @staticmethod
    def _draw_debug(
        image: np.ndarray,
        corners: np.ndarray,
        tag_id: int,
        rvec: np.ndarray,
        tvec: np.ndarray,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ):
        """
        在调试图像上画出：
        1. 标签边框
        2. 标签 ID
        3. 坐标轴
        4. 平移向量文本
        """
        corners_i = corners.astype(int)

        for i in range(4):
            p1 = tuple(corners_i[i])
            p2 = tuple(corners_i[(i + 1) % 4])
            cv2.line(image, p1, p2, (0, 255, 0), 2)

        center = np.mean(corners, axis=0).astype(int)
        cv2.putText(
            image,
            f"ID={tag_id}",
            tuple(center),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
            cv2.LINE_AA
        )

        # 画相机坐标轴
        cv2.drawFrameAxes(
            image,
            camera_matrix,
            dist_coeffs,
            rvec,
            tvec,
            0.05
        )

        text = f"x={tvec[0,0]:.3f} y={tvec[1,0]:.3f} z={tvec[2,0]:.3f} m"
        cv2.putText(
            image,
            text,
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2,
            cv2.LINE_AA
        )