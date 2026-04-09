#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage 1: 数据链路验证脚本

目标:
1. 验证是否能稳定接收 ZED 的 RGB 图像
2. 验证是否能稳定接收 CameraInfo
3. 验证是否能稳定接收 PointCloud2
4. 输出当前数据链路状态、频率、超时告警

说明:
- 本阶段不做任何视觉算法
- 本阶段不做标定板检测
- 本阶段不做地面拟合
- 只做“节点 + 订阅 + 状态验证”
"""

import os

# 必须尽量放在 import rclpy 之前
os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"
os.environ["FASTDDS_BUILTIN_TRANSPORTS"] = "UDPv4"

import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image, CameraInfo, PointCloud2

# 允许从项目根目录导入 modules
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.ros_interfaces import load_yaml_config, ros_stamp_to_sec


class DataStreamMonitor:
    """
    用于监控单一路数据流状态。

    功能:
    - 统计总消息数
    - 记录最近一次接收时间
    - 估算接收频率
    """

    def __init__(self, name: str, max_samples: int = 50):
        self.name = name
        self.count = 0
        self.last_recv_wall_time: Optional[float] = None
        self.last_msg_stamp: Optional[float] = None
        self.intervals = deque(maxlen=max_samples)

    def update(self, msg_stamp_sec: Optional[float] = None):
        """
        更新数据流状态。

        参数:
            msg_stamp_sec: ROS 消息头时间戳（秒），可选
        """
        now = time.time()

        if self.last_recv_wall_time is not None:
            interval = now - self.last_recv_wall_time
            if interval > 0:
                self.intervals.append(interval)

        self.last_recv_wall_time = now
        self.last_msg_stamp = msg_stamp_sec
        self.count += 1

    def get_frequency(self) -> float:
        """
        通过最近若干次接收间隔估算频率。
        """
        if len(self.intervals) == 0:
            return 0.0

        avg_interval = sum(self.intervals) / len(self.intervals)
        if avg_interval <= 0:
            return 0.0

        return 1.0 / avg_interval

    def get_age(self) -> Optional[float]:
        """
        返回距离最近一次接收已经过去多久（秒）。
        """
        if self.last_recv_wall_time is None:
            return None
        return time.time() - self.last_recv_wall_time

    def has_received(self) -> bool:
        return self.count > 0


class Stage1DataProbeNode(Node):
    """
    第一阶段数据链路验证节点。
    """

    def __init__(self, config_path: str):
        self.cfg = load_yaml_config(config_path)

        node_name = self.cfg.get("runtime", {}).get("node_name", "stage1_data_probe")
        super().__init__(node_name)

        # 读取配置
        zed_cfg = self.cfg.get("zed", {})
        runtime_cfg = self.cfg.get("runtime", {})

        self.image_topic = zed_cfg.get("image_topic", "/zed/zed_node/rgb/image_rect_color")
        self.camera_info_topic = zed_cfg.get("camera_info_topic", "/zed/zed_node/rgb/camera_info")
        self.pointcloud_topic = zed_cfg.get("pointcloud_topic", "/zed/zed_node/point_cloud/cloud_registered")

        self.report_interval_sec = float(runtime_cfg.get("report_interval_sec", 2.0))
        self.timeout_warn_sec = float(runtime_cfg.get("timeout_warn_sec", 1.0))

        # 三路数据监控器
        self.image_monitor = DataStreamMonitor("image")
        self.camera_info_monitor = DataStreamMonitor("camera_info")
        self.pointcloud_monitor = DataStreamMonitor("pointcloud")

        # 缓存少量关键信息，仅用于打印
        self.last_image_shape = None
        self.last_camera_info = None
        self.last_pointcloud_meta = None

        # 订阅器
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

        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            self.pointcloud_topic,
            self.pointcloud_callback,
            10
        )

        # 定时状态输出
        self.report_timer = self.create_timer(
            self.report_interval_sec,
            self.report_status
        )

        self.get_logger().info("========================================")
        self.get_logger().info("Stage 1 Data Probe Node Started")
        self.get_logger().info(f"Image topic      : {self.image_topic}")
        self.get_logger().info(f"CameraInfo topic : {self.camera_info_topic}")
        self.get_logger().info(f"PointCloud topic : {self.pointcloud_topic}")
        self.get_logger().info("========================================")

    def image_callback(self, msg: Image):
        """
        RGB 图像回调。

        当前阶段只记录:
        - 是否收到图像
        - 图像尺寸
        - 编码格式
        - 接收频率
        """
        stamp_sec = ros_stamp_to_sec(msg.header.stamp)
        self.image_monitor.update(stamp_sec)

        self.last_image_shape = {
            "width": msg.width,
            "height": msg.height,
            "encoding": msg.encoding,
            "frame_id": msg.header.frame_id,
        }

    def camera_info_callback(self, msg: CameraInfo):
        """
        相机内参回调。

        当前阶段只记录:
        - 是否收到 CameraInfo
        - 图像宽高
        - K 矩阵关键参数 fx, fy, cx, cy
        """
        stamp_sec = ros_stamp_to_sec(msg.header.stamp)
        self.camera_info_monitor.update(stamp_sec)

        fx = msg.k[0]
        fy = msg.k[4]
        cx = msg.k[2]
        cy = msg.k[5]

        self.last_camera_info = {
            "width": msg.width,
            "height": msg.height,
            "fx": fx,
            "fy": fy,
            "cx": cx,
            "cy": cy,
            "frame_id": msg.header.frame_id,
        }

    def pointcloud_callback(self, msg: PointCloud2):
        """
        点云回调。

        当前阶段只记录:
        - 是否收到点云
        - 点云宽高
        - frame_id
        - point_step / row_step
        """
        stamp_sec = ros_stamp_to_sec(msg.header.stamp)
        self.pointcloud_monitor.update(stamp_sec)

        self.last_pointcloud_meta = {
            "width": msg.width,
            "height": msg.height,
            "point_step": msg.point_step,
            "row_step": msg.row_step,
            "is_dense": msg.is_dense,
            "frame_id": msg.header.frame_id,
        }

    def format_stream_status(self, monitor: DataStreamMonitor) -> str:
        """
        格式化单一路数据流状态，便于统一打印。
        """
        if not monitor.has_received():
            return f"{monitor.name}: NOT RECEIVED"

        freq = monitor.get_frequency()
        age = monitor.get_age()

        status = f"{monitor.name}: OK | count={monitor.count} | freq={freq:.2f} Hz"

        if age is not None:
            status += f" | last_age={age:.3f} s"
            if age > self.timeout_warn_sec:
                status += " | WARNING: timeout"

        return status

    def report_status(self):
        """
        周期性打印状态报告。

        目标:
        - 判断三类数据是否都已收到
        - 判断是否掉流
        - 打印最近一次消息的基础元数据
        """
        self.get_logger().info("--------------- Data Link Status ---------------")
        self.get_logger().info(self.format_stream_status(self.image_monitor))
        self.get_logger().info(self.format_stream_status(self.camera_info_monitor))
        self.get_logger().info(self.format_stream_status(self.pointcloud_monitor))

        if self.last_image_shape is not None:
            self.get_logger().info(
                f"[Image] width={self.last_image_shape['width']}, "
                f"height={self.last_image_shape['height']}, "
                f"encoding={self.last_image_shape['encoding']}, "
                f"frame_id={self.last_image_shape['frame_id']}"
            )

        if self.last_camera_info is not None:
            self.get_logger().info(
                f"[CameraInfo] width={self.last_camera_info['width']}, "
                f"height={self.last_camera_info['height']}, "
                f"fx={self.last_camera_info['fx']:.3f}, "
                f"fy={self.last_camera_info['fy']:.3f}, "
                f"cx={self.last_camera_info['cx']:.3f}, "
                f"cy={self.last_camera_info['cy']:.3f}, "
                f"frame_id={self.last_camera_info['frame_id']}"
            )

        if self.last_pointcloud_meta is not None:
            self.get_logger().info(
                f"[PointCloud] width={self.last_pointcloud_meta['width']}, "
                f"height={self.last_pointcloud_meta['height']}, "
                f"point_step={self.last_pointcloud_meta['point_step']}, "
                f"row_step={self.last_pointcloud_meta['row_step']}, "
                f"is_dense={self.last_pointcloud_meta['is_dense']}, "
                f"frame_id={self.last_pointcloud_meta['frame_id']}"
            )

        all_received = (
            self.image_monitor.has_received()
            and self.camera_info_monitor.has_received()
            and self.pointcloud_monitor.has_received()
        )

        if all_received:
            self.get_logger().info("Stage 1 readiness: PASS (all required streams received)")
        else:
            self.get_logger().warn("Stage 1 readiness: WAITING (some streams not received yet)")

        self.get_logger().info("------------------------------------------------")


def main():
    """
    主函数。
    """
    rclpy.init()

    config_path = os.path.join(PROJECT_ROOT, "config", "topics.yaml")

    node = None
    try:
        node = Stage1DataProbeNode(config_path=config_path)
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received, shutting down...")
    except Exception as e:
        print(f"[ERROR] Exception in Stage1DataProbeNode: {e}")
        raise
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()