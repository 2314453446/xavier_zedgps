#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.environ.setdefault("ROS_DOMAIN_ID", "0")
os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")
os.environ.setdefault("FASTDDS_BUILTIN_TRANSPORTS", "UDPv4")
os.environ.setdefault("ROS_LOCALHOST_ONLY", "0")

import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2

from modules.ros_interfaces import load_yaml_config
from modules.ground_plane import (
    organized_pointcloud2_to_xyz_image,
    fit_ground_plane_from_pixel_roi,
)
from modules.ground_plane_viewer import GroundPlaneDebugViewer


class Stage4GroundPlaneNode(Node):
    """
    Step 4 主节点：
    1. 订阅 RGB 图像
    2. 订阅 organized PointCloud2
    3. 按 RGB 像素 ROI 提取候选地面点
    4. 用 RANSAC 拟合地面平面
    5. 输出平面参数和拟合统计
    """

    def __init__(self, topics_cfg_path: str, ground_cfg_path: str):
        topics_cfg = load_yaml_config(topics_cfg_path)
        ground_cfg = load_yaml_config(ground_cfg_path)

        runtime_cfg = ground_cfg.get("runtime", {})
        node_name = runtime_cfg.get("node_name", "stage4_ground_plane")
        super().__init__(node_name)

        self.prev_plane_normal = None

        self.cfg = ground_cfg

        self.image_topic = topics_cfg["zed"]["image_topic"]
        self.pointcloud_topic = topics_cfg["zed"]["pointcloud_topic"]

        self.report_interval_sec = float(runtime_cfg.get("report_interval_sec", 1.0))
        self.show_debug_window = bool(runtime_cfg.get("show_debug_window", True))
        self.show_plane_3d_viewer = bool(runtime_cfg.get("show_plane_3d_viewer", True))
        self.plane_patch_extent_m = float(runtime_cfg.get("plane_patch_extent_m", 0.4))
        self.viewer_max_draw_points = int(runtime_cfg.get("viewer_max_draw_points", 3000))

        self.plane_viewer = None
        if self.show_plane_3d_viewer:
            self.plane_viewer = GroundPlaneDebugViewer(
                plane_extent=self.plane_patch_extent_m,
                max_draw_points=self.viewer_max_draw_points
            )

        self.latest_image_msg = None
        self.latest_pointcloud_msg = None

        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            10
        )

        self.pc_sub = self.create_subscription(
            PointCloud2,
            self.pointcloud_topic,
            self.pointcloud_callback,
            10
        )

        self.timer = self.create_timer(self.report_interval_sec, self.process_once)

        self.get_logger().info("========================================")
        self.get_logger().info("Stage 4 Ground Plane Node Started")
        self.get_logger().info(f"Image topic      : {self.image_topic}")
        self.get_logger().info(f"PointCloud topic : {self.pointcloud_topic}")
        self.get_logger().info("========================================")

    def stabilize_plane_normal_with_previous(self, plane: np.ndarray) -> np.ndarray:
        """
        让当前法向和上一帧尽量保持同向。
        """
        normal = plane[:3]

        if self.prev_plane_normal is not None:
            if np.dot(normal, self.prev_plane_normal) < 0:
                plane = -plane
                normal = -normal

        self.prev_plane_normal = normal.copy()
        return plane

    def image_callback(self, msg: Image):
        self.latest_image_msg = msg

    def pointcloud_callback(self, msg: PointCloud2):
        self.latest_pointcloud_msg = msg

    def process_once(self):
        if self.latest_image_msg is None or self.latest_pointcloud_msg is None:
            self.get_logger().warn("Waiting for image and point cloud...")
            return

        try:
            image_bgr = self.ros_image_to_bgr(self.latest_image_msg)

            xyz_image = organized_pointcloud2_to_xyz_image(self.latest_pointcloud_msg)

            result = fit_ground_plane_from_pixel_roi(
                xyz_image=xyz_image,
                cfg=self.cfg,
                frame_id=self.latest_pointcloud_msg.header.frame_id
            )

            debug_image = image_bgr.copy()
            self.draw_pixel_roi(debug_image)

            if not result.success:
                self.get_logger().warn(f"Ground plane fit failed: {result.message}")
                if self.show_debug_window:
                    cv2.imshow("stage4_ground_plane_debug", debug_image)
                    cv2.waitKey(1)
                return

            plane = self.stabilize_plane_normal_with_previous(result.plane.copy())
            normal = plane[:3]
            result.plane = plane
            result.normal = normal

            roi_n = len(result.roi_points) if result.roi_points is not None else 0
            inlier_n = len(result.inlier_points) if result.inlier_points is not None else 0

            distances = np.abs(result.inlier_points @ plane[:3] + plane[3])
            mean_residual = float(np.mean(distances)) if len(distances) > 0 else 0.0

            self.get_logger().info(
                f"Ground plane fitted | frame={result.frame_id} | "
                f"plane=({plane[0]:.5f}, {plane[1]:.5f}, {plane[2]:.5f}, {plane[3]:.5f}) | "
                f"normal=({normal[0]:.5f}, {normal[1]:.5f}, {normal[2]:.5f}) | "
                f"roi_points={roi_n} | inliers={inlier_n} | mean_residual={mean_residual:.5f} m"
            )

            self.draw_plane_info(debug_image, plane, normal, roi_n, inlier_n, mean_residual)

            if self.plane_viewer is not None:
                self.plane_viewer.update(
                    roi_points=result.roi_points,
                    inlier_points=result.inlier_points,
                    plane=result.plane,
                    normal=result.normal,
                )

            if self.show_debug_window:
                cv2.imshow("stage4_ground_plane_debug", debug_image)
                cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f"process_once failed: {e}")

    def draw_pixel_roi(self, image: np.ndarray):
        """
        在 RGB 图像上画出当前使用的像素 ROI。
        """
        gcfg = self.cfg.get("ground", {})
        u_min = int(gcfg.get("u_min", 0))
        u_max = int(gcfg.get("u_max", image.shape[1] - 1))
        v_min = int(gcfg.get("v_min", 0))
        v_max = int(gcfg.get("v_max", image.shape[0] - 1))

        cv2.rectangle(image, (u_min, v_min), (u_max, v_max), (0, 255, 255), 2)
        cv2.putText(
            image,
            "GROUND ROI",
            (u_min + 5, max(v_min - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA
        )

    @staticmethod
    def draw_plane_info(
        image: np.ndarray,
        plane: np.ndarray,
        normal: np.ndarray,
        roi_n: int,
        inlier_n: int,
        mean_residual: float
    ):
        """
        在调试图像上叠加拟合结果文本。
        """
        texts = [
            f"plane: a={plane[0]:.4f}, b={plane[1]:.4f}, c={plane[2]:.4f}, d={plane[3]:.4f}",
            f"normal: ({normal[0]:.4f}, {normal[1]:.4f}, {normal[2]:.4f})",
            f"roi_points={roi_n}, inliers={inlier_n}, mean_residual={mean_residual:.4f} m",
        ]

        y0 = 30
        for i, text in enumerate(texts):
            y = y0 + i * 28
            cv2.putText(
                image,
                text,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )

    @staticmethod
    def ros_image_to_bgr(msg: Image) -> np.ndarray:
        h = msg.height
        w = msg.width

        if msg.encoding == "bgra8":
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 4)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        if msg.encoding == "bgr8":
            return np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 3)

        if msg.encoding == "rgb8":
            rgb = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 3)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        raise ValueError(f"Unsupported image encoding: {msg.encoding}")


def main():
    rclpy.init()
    node = None

    try:
        topics_cfg_path = str(PROJECT_ROOT / "config" / "topics.yaml")
        ground_cfg_path = str(PROJECT_ROOT / "config" / "ground_plane.yaml")

        node = Stage4GroundPlaneNode(topics_cfg_path, ground_cfg_path)
        rclpy.spin(node)

    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received, shutting down...")
    finally:
        if node is not None:
            node.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()


if __name__ == "__main__":
    main()