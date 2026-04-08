# plane_normal_bridge.py
import pyzed.sl as sl
import numpy as np

# 全局保存最近一次法向量信息
latest_plane_data = {"center": None, "normal": None}

def detect_plane(zed, click_x, click_y):
    """基于点击坐标检测平面并更新法向量"""
    plane = sl.Plane()
    err = zed.find_plane_at_hit([click_x, click_y], plane)
    if err == sl.ERROR_CODE.SUCCESS:
        center = np.array(plane.get_center())
        normal = np.array(plane.get_normal())
        latest_plane_data["center"] = center
        latest_plane_data["normal"] = normal
        print(f"[Bridge] Plane detected center={center}, normal={normal}")
        return center, normal
    else:
        print("[Bridge] Plane detection failed:", err)
        return None, None

def get_latest_plane():
    """供 viewer 读取当前平面法向量"""
    return latest_plane_data["center"], latest_plane_data["normal"]
