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
from sensor_msgs.msg import Image, CameraInfo

from modules.ros_interfaces import load_yaml_config
from modules.board_detector import AprilTagBoardDetector


class Stage2BoardPoseNode(Node):
    """
    Step 2 主节点：
    - 订阅 RGB 图像
    - 订阅 CameraInfo
    - 调用板检测模块
    - 输出板位姿
    """

    def __init__(self, topics_cfg_path: str, board_cfg_path: str):
        topics_cfg = load_yaml_config(topics_cfg_path)
        board_cfg = load_yaml_config(board_cfg_path)

        node_name = board_cfg.get("runtime", {}).get("node_name", "stage2_board_pose")
        super().__init__(node_name)

        self.image_topic = topics_cfg["zed"]["image_topic"]
        self.camera_info_topic = topics_cfg["zed"]["camera_info_topic"]

        runtime_cfg = board_cfg.get("runtime", {})
        self.report_interval_sec = float(runtime_cfg.get("report_interval_sec", 1.0))
        self.show_window = bool(runtime_cfg.get("show_window", True))

        self.detector = AprilTagBoardDetector(board_cfg)

        self.latest_image_msg = None
        self.latest_camera_info_msg = None

        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            10
        )

        self.timer = self.create_timer(
            self.report_interval_sec,
            self.process_once
        )

        self.get_logger().info("========================================")
        self.get_logger().info("Stage 2 Board Pose Node Started")
        self.get_logger().info(f"Image topic      : {self.image_topic}")
        self.get_logger().info(f"CameraInfo topic : {self.camera_info_topic}")
        self.get_logger().info("========================================")

    def image_callback(self, msg: Image):
        """
        缓存最新图像。
        第一版只保留最后一帧，不做时间同步。
        """
        self.latest_image_msg = msg

    def camera_info_callback(self, msg: CameraInfo):
        """
        缓存最新相机内参。
        """
        self.latest_camera_info_msg = msg

    def process_once(self):
        """
        周期执行一次板检测。
        """
        if self.latest_image_msg is None or self.latest_camera_info_msg is None:
            self.get_logger().warn("Waiting for image and camera info...")
            return

        try:
            image_bgr = self.ros_image_to_bgr(self.latest_image_msg)
            camera_matrix, dist_coeffs = self.camera_info_to_matrices(self.latest_camera_info_msg)

            result = self.detector.detect(image_bgr, camera_matrix, dist_coeffs)

            if result.detected:
                tvec = result.tvec.reshape(-1)
                rvec = result.rvec.reshape(-1)

                self.get_logger().info(
                    f"Board detected | family={result.family} | id={result.tag_id} | "
                    f"tvec=({tvec[0]:.4f}, {tvec[1]:.4f}, {tvec[2]:.4f}) m | "
                    f"rvec=({rvec[0]:.4f}, {rvec[1]:.4f}, {rvec[2]:.4f})"
                )
            else:
                self.get_logger().warn(f"Board not detected: {result.message}")

            if self.show_window and result.debug_image is not None:
                cv2.imshow("stage2_board_pose_debug", result.debug_image)
                cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f"process_once failed: {e}")

    @staticmethod
    def ros_image_to_bgr(msg: Image) -> np.ndarray:
        """
        将 ROS Image 转换成 OpenCV BGR 图像。

        你在 Step 1 已经确认 image encoding 是 bgra8，
        所以这里优先处理 bgra8。
        """
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
        """
        将 CameraInfo 转成 OpenCV 使用的内参与畸变参数。
        """
        camera_matrix = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        dist_coeffs = np.array(msg.d, dtype=np.float64).reshape(-1, 1)
        return camera_matrix, dist_coeffs


def main():
    rclpy.init()
    node = None

    try:
        topics_cfg_path = str(PROJECT_ROOT / "config" / "topics.yaml")
        board_cfg_path = str(PROJECT_ROOT / "config" / "board.yaml")

        node = Stage2BoardPoseNode(topics_cfg_path, board_cfg_path)
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