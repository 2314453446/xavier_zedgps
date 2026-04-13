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
from sensor_msgs.msg import Image, CameraInfo, PointCloud2

from modules.ros_interfaces import load_yaml_config
from modules.board_detector import AprilTagBoardDetector
from modules.tool_transform import transform_tool_point, project_point_to_image
from modules.ground_plane import (
    organized_pointcloud2_to_xyz_image,
    fit_ground_plane_from_pixel_roi,
)
from modules.depth_estimator import compute_depth, ExponentialSmoother


class Stage5DepthEstimatorNode(Node):
    """
    Step 5 主节点：
    1. 检测板位姿
    2. 解算犁耙测量点
    3. 拟合地面平面
    4. 统一坐标系
    5. 计算 signed_dist 和 depth
    """

    def __init__(self, topics_cfg_path, board_cfg_path, tool_cfg_path, ground_cfg_path, depth_cfg_path):
        topics_cfg = load_yaml_config(topics_cfg_path)
        board_cfg = load_yaml_config(board_cfg_path)
        tool_cfg = load_yaml_config(tool_cfg_path)
        ground_cfg = load_yaml_config(ground_cfg_path)
        depth_cfg = load_yaml_config(depth_cfg_path)

        runtime_cfg = depth_cfg.get("runtime", {})
        node_name = runtime_cfg.get("node_name", "stage5_depth_estimator")
        super().__init__(node_name)

        self.board_cfg = board_cfg
        self.tool_cfg = tool_cfg
        self.ground_cfg = ground_cfg
        self.depth_cfg = depth_cfg

        self.image_topic = topics_cfg["zed"]["image_topic"]
        self.camera_info_topic = topics_cfg["zed"]["camera_info_topic"]
        self.pointcloud_topic = topics_cfg["zed"]["pointcloud_topic"]

        self.report_interval_sec = float(runtime_cfg.get("report_interval_sec", 1.0))
        self.show_debug_window = bool(runtime_cfg.get("show_debug_window", True))

        self.point_in_board = np.array(
            self.tool_cfg["tool"]["point_in_board_m"],
            dtype=np.float64
        ).reshape(3)

        alpha = float(self.depth_cfg.get("depth", {}).get("smooth_alpha", 0.3))
        self.depth_smoother = ExponentialSmoother(alpha=alpha)

        self.detector = AprilTagBoardDetector(self.board_cfg)

        self.latest_image_msg = None
        self.latest_camera_info_msg = None
        self.latest_pointcloud_msg = None

        self.image_sub = self.create_subscription(Image, self.image_topic, self.image_callback, 10)
        self.camera_info_sub = self.create_subscription(CameraInfo, self.camera_info_topic, self.camera_info_callback, 10)
        self.pc_sub = self.create_subscription(PointCloud2, self.pointcloud_topic, self.pointcloud_callback, 10)

        self.timer = self.create_timer(self.report_interval_sec, self.process_once)

        self.get_logger().info("========================================")
        self.get_logger().info("Stage 5 Depth Estimator Node Started")
        self.get_logger().info(f"Image topic      : {self.image_topic}")
        self.get_logger().info(f"CameraInfo topic : {self.camera_info_topic}")
        self.get_logger().info(f"PointCloud topic : {self.pointcloud_topic}")
        self.get_logger().info(f"point_in_board_m : {self.point_in_board.tolist()}")
        self.get_logger().info("========================================")

    def image_callback(self, msg: Image):
        self.latest_image_msg = msg

    def camera_info_callback(self, msg: CameraInfo):
        self.latest_camera_info_msg = msg

    def pointcloud_callback(self, msg: PointCloud2):
        self.latest_pointcloud_msg = msg

    def process_once(self):
        if (
            self.latest_image_msg is None
            or self.latest_camera_info_msg is None
            or self.latest_pointcloud_msg is None
        ):
            self.get_logger().warn("Waiting for image / camera_info / pointcloud ...")
            return

        try:
            image_bgr = self.ros_image_to_bgr(self.latest_image_msg)
            camera_matrix, dist_coeffs = self.camera_info_to_matrices(self.latest_camera_info_msg)

            # ---------- Step 2 ----------
            board_result = self.detector.detect(image_bgr, camera_matrix, dist_coeffs)
            debug_image = board_result.debug_image if board_result.debug_image is not None else image_bgr.copy()

            if not board_result.detected:
                self.get_logger().warn(f"Board not detected: {board_result.message}")
                self.show_debug(debug_image)
                return

            # ---------- Step 3 ----------
            tool_result = transform_tool_point(
                rvec=board_result.rvec,
                tvec=board_result.tvec,
                point_in_board=self.point_in_board
            )

            if not tool_result.success:
                self.get_logger().error(tool_result.message)
                self.show_debug(debug_image)
                return

            point_optical = tool_result.point_in_camera
            uv = project_point_to_image(point_optical, camera_matrix, dist_coeffs)

            # ---------- Step 4 ----------
            xyz_image = organized_pointcloud2_to_xyz_image(self.latest_pointcloud_msg)
            plane_result = fit_ground_plane_from_pixel_roi(
                xyz_image=xyz_image,
                cfg=self.ground_cfg,
                frame_id=self.latest_pointcloud_msg.header.frame_id
            )

            if not plane_result.success:
                self.get_logger().warn(f"Ground plane fit failed: {plane_result.message}")
                self.draw_tool_point(debug_image, uv, point_optical)
                self.show_debug(debug_image)
                return

            # ---------- Step 5 ----------
            depth_result = compute_depth(
                point_optical=point_optical,
                plane_camera=plane_result.plane,
                cfg=self.depth_cfg
            )

            if not depth_result.success:
                self.get_logger().error(depth_result.message)
                self.draw_tool_point(debug_image, uv, point_optical)
                self.show_debug(debug_image)
                return

            smoothed_depth = self.depth_smoother.update(depth_result.depth)

            self.get_logger().info(
                f"Depth computed | "
                f"point_opt=({depth_result.point_optical[0]:.4f}, {depth_result.point_optical[1]:.4f}, {depth_result.point_optical[2]:.4f}) m | "
                f"point_cam=({depth_result.point_camera[0]:.4f}, {depth_result.point_camera[1]:.4f}, {depth_result.point_camera[2]:.4f}) m | "
                f"signed_dist={depth_result.signed_dist:.5f} m | "
                f"depth_raw={depth_result.depth:.5f} m | "
                f"depth_smooth={smoothed_depth:.5f} m"
            )

            self.draw_tool_point(debug_image, uv, point_optical)
            self.draw_depth_info(
                debug_image,
                signed_dist=depth_result.signed_dist,
                depth_raw=depth_result.depth,
                depth_smooth=smoothed_depth
            )
            self.show_debug(debug_image)

        except Exception as e:
            self.get_logger().error(f"process_once failed: {e}")

    def draw_tool_point(self, image: np.ndarray, uv: np.ndarray, point_optical: np.ndarray):
        u, v = int(round(uv[0])), int(round(uv[1]))
        cv2.circle(image, (u, v), 8, (0, 255, 255), -1)
        cv2.putText(
            image,
            "TOOL_POINT",
            (u + 10, v - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA
        )

        text = f"Optical XYZ=({point_optical[0]:.3f}, {point_optical[1]:.3f}, {point_optical[2]:.3f})"
        cv2.putText(
            image,
            text,
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA
        )

    @staticmethod
    def draw_depth_info(image: np.ndarray, signed_dist: float, depth_raw: float, depth_smooth: float):
        texts = [
            f"signed_dist = {signed_dist:.4f} m",
            f"depth_raw   = {depth_raw:.4f} m",
            f"depth_smooth= {depth_smooth:.4f} m",
        ]
        y0 = 95
        for i, text in enumerate(texts):
            y = y0 + i * 28
            cv2.putText(
                image,
                text,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )

    def show_debug(self, image: np.ndarray):
        if self.show_debug_window:
            cv2.imshow("stage5_depth_estimator_debug", image)
            cv2.waitKey(1)

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

    @staticmethod
    def camera_info_to_matrices(msg: CameraInfo):
        camera_matrix = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        dist_coeffs = np.array(msg.d, dtype=np.float64).reshape(-1, 1)
        return camera_matrix, dist_coeffs


def main():
    rclpy.init()
    node = None

    try:
        node = Stage5DepthEstimatorNode(
            topics_cfg_path=str(PROJECT_ROOT / "config" / "topics.yaml"),
            board_cfg_path=str(PROJECT_ROOT / "config" / "board.yaml"),
            tool_cfg_path=str(PROJECT_ROOT / "config" / "tool.yaml"),
            ground_cfg_path=str(PROJECT_ROOT / "config" / "ground_plane.yaml"),
            depth_cfg_path=str(PROJECT_ROOT / "config" / "depth.yaml"),
        )
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