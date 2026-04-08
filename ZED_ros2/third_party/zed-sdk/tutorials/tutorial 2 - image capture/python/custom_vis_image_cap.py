########################################################################
# 可视化 ZED 左目图像并叠加时间戳/FPS/分辨率
########################################################################
import pyzed.sl as sl
import cv2
import time
from datetime import datetime

def main():
    # 1) 打开相机
    zed = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.AUTO
    init_params.camera_fps = 30

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Camera open failed. Exit.")
        return

    runtime = sl.RuntimeParameters()
    image = sl.Mat()

    # 2) 采集显示（最多 500 帧，可按 q 提前退出）
    i = 0
    prev_t = None
    cv2.namedWindow("ZED LEFT (with timestamp)", cv2.WINDOW_NORMAL)

    while i < 500:
        if zed.grab(runtime) == sl.ERROR_CODE.SUCCESS:
            # 注意：使用 IMAGE 时间参考，获得该帧的采集时间戳
            ts = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE)
            ms = ts.get_milliseconds()  # UNIX epoch 毫秒
            # 人类可读的本地时间（例如 KST）
            human_time = datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # 取左目图像（RGBA），转 BGR 便于 OpenCV 显示
            zed.retrieve_image(image, sl.VIEW.LEFT)
            frame_rgba = image.get_data()  # H x W x 4 (RGBA)
            frame_bgr = cv2.cvtColor(frame_rgba, cv2.COLOR_RGBA2BGR)

            # 计算 FPS
            now = time.time()
            if prev_t is None:
                fps = 0.0
            else:
                dt = now - prev_t
                fps = 1.0 / dt if dt > 0 else 0.0
            prev_t = now

            h, w = frame_bgr.shape[:2]

            # 3) 叠加文字信息（时间戳、分辨率、FPS）
            line1 = f"Time: {human_time}"
            line2 = f"UNIX(ms): {ms}"
            line3 = f"Res: {w}x{h} | FPS: {fps:.1f}"

            y0 = 30
            dy = 28
            for idx, text in enumerate([line1, line2, line3]):
                y = y0 + idx * dy
                # 先画黑底再画白字提高可读性
                cv2.putText(frame_bgr, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 3, cv2.LINE_AA)
                cv2.putText(frame_bgr, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 1, cv2.LINE_AA)

            cv2.imshow("ZED LEFT (with timestamp)", frame_bgr)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

            i += 1

    # 4) 关闭
    cv2.destroyAllWindows()
    zed.close()

if __name__ == "__main__":
    main()
