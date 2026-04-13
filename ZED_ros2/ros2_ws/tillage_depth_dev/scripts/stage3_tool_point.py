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
from modules.tool_transform import transform_tool_point, project_point_to_image


class Stage3ToolPointNode(Node):
    """
    Step 3 主节点：
    1. 复用 Step 2 的板检测结果
    2. 读取板坐标系下固定点 p_B
    3. 计算相机坐标系下的犁耙测量点 p_C
    4. 将 p_C 回投影到图像上做调试显示
    """

    def __init__(self, topics_cfg_path: str, board_cfg_path: str, tool_cfg_path: str):
        topics_cfg = load_yaml_config(topics_cfg_path)
        board_cfg = load_yaml_config(board_cfg_path)
        tool_cfg = load_yaml_config(tool_cfg_path)

        runtime_cfg = tool_cfg.get("runtime", {})
        node_name = runtime_cfg.get("node_name", "stage3_tool_point")
        super().__init__(node_name)

        self.image_topic = topics_cfg["zed"]["image_topic"]
        self.camera_info_topic = topics_cfg["zed"]["camera_info_topic"]

        self.report_interval_sec = float(runtime_cfg.get("report_interval_sec", 1.0))
        self.show_window = bool(runtime_cfg.get("show_window", True))

        self.point_in_board = np.array(
            tool_cfg["tool"]["point_in_board_m"],
            dtype=np.float64
        ).reshape(3)

        self.detector = AprilTagBoardDetector(board_cfg)

        self.latest_image_msg = None
        self.latest_camera_info_msg = None

        self.image_sub = self.create_subscription(
            Image, self.image_topic, self.image_callback, 10
        )
        self.camera_info_sub = self.create_subscription(
            CameraInfo, self.camera_info_topic, self.camera_info_callback, 10
        )

        self.timer = self.create_timer(self.report_interval_sec, self.process_once)

        self.get_logger().info("========================================")
        self.get_logger().info("Stage 3 Tool Point Node Started")
        self.get_logger().info(f"Image topic      : {self.image_topic}")
        self.get_logger().info(f"CameraInfo topic : {self.camera_info_topic}")
        self.get_logger().info(f"point_in_board_m : {self.point_in_board.tolist()}")
        self.get_logger().info("========================================")

    def image_callback(self, msg: Image):
        self.latest_image_msg = msg

    def camera_info_callback(self, msg: CameraInfo):
        self.latest_camera_info_msg = msg

    def process_once(self):
        if self.latest_image_msg is None or self.latest_camera_info_msg is None:
            self.get_logger().warn("Waiting for image and camera info...")
            return

        try:
            image_bgr = self.ros_image_to_bgr(self.latest_image_msg)
            camera_matrix, dist_coeffs = self.camera_info_to_matrices(self.latest_camera_info_msg)

            board_result = self.detector.detect(image_bgr, camera_matrix, dist_coeffs)

            debug_image = board_result.debug_image if board_result.debug_image is not None else image_bgr.copy()

            if not board_result.detected:
                self.get_logger().warn(f"Board not detected: {board_result.message}")
                if self.show_window:
                    cv2.imshow("stage3_tool_point_debug", debug_image)
                    cv2.waitKey(1)
                return

            tool_result = transform_tool_point(
                rvec=board_result.rvec,
                tvec=board_result.tvec,
                point_in_board=self.point_in_board
            )

            if not tool_result.success:
                self.get_logger().error(tool_result.message)
                if self.show_window:
                    cv2.imshow("stage3_tool_point_debug", debug_image)
                    cv2.waitKey(1)
                return

            p_C = tool_result.point_in_camera
            uv = project_point_to_image(p_C, camera_matrix, dist_coeffs)

            self.get_logger().info(
                "Tool point solved | "
                f"p_B=({self.point_in_board[0]:.4f}, {self.point_in_board[1]:.4f}, {self.point_in_board[2]:.4f}) m | "
                f"p_C=({p_C[0]:.4f}, {p_C[1]:.4f}, {p_C[2]:.4f}) m | "
                f"uv=({uv[0]:.1f}, {uv[1]:.1f}) px"
            )

            self.draw_tool_point(debug_image, uv, p_C)

            if self.show_window:
                cv2.imshow("stage3_tool_point_debug", debug_image)
                cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f"process_once failed: {e}")

    @staticmethod
    def draw_tool_point(image: np.ndarray, uv: np.ndarray, p_C: np.ndarray):
        """
        在调试图像上画出预测的犁耙测量点
        """
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

        text = f"X={p_C[0]:.3f} Y={p_C[1]:.3f} Z={p_C[2]:.3f} m"
        cv2.putText(
            image,
            text,
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
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

    @staticmethod
    def camera_info_to_matrices(msg: CameraInfo):
        camera_matrix = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        dist_coeffs = np.array(msg.d, dtype=np.float64).reshape(-1, 1)
        return camera_matrix, dist_coeffs


def main():
    rclpy.init()
    node = None

    try:
        topics_cfg_path = str(PROJECT_ROOT / "config" / "topics.yaml")
        board_cfg_path = str(PROJECT_ROOT / "config" / "board.yaml")
        tool_cfg_path = str(PROJECT_ROOT / "config" / "tool.yaml")

        node = Stage3ToolPointNode(topics_cfg_path, board_cfg_path, tool_cfg_path)
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