import threading
import time
import pyzed.sl as sl
from gpsdclient import GPSDClient
import random
import datetime


class GPSDReader:
    def __init__(self):
        self.continue_to_grab = True
        self.new_data = False
        self.is_initialized = False
        self.current_gnss_data = None
        self.is_initialized_mtx = threading.Lock()
        self.client = None
        self.gnss_getter = None
        self.grab_gnss_data = None
        self.last_gnss_time_us = None
        self.last_covariance = None

    def initialize(self):
        try:
            self.client = GPSDClient(host="127.0.0.1")
        except:
            print("No GPSD running .. exit")
            return -1

        self.grab_gnss_data = threading.Thread(target=self.grabGNSSData)
        self.grab_gnss_data.start()
        print("Successfully connected to GPSD")
        print("Waiting for GNSS fix")
        received_fix = False

        self.gnss_getter = self.client.dict_stream(convert_datetime=True, filter=["TPV"])
        while not received_fix:
            gpsd_data = next(self.gnss_getter)
            if "class" in gpsd_data and gpsd_data["class"] == "TPV" and "mode" in gpsd_data and gpsd_data["mode"] >= 2:
                received_fix = True
        print("Fix found !!!")
        with self.is_initialized_mtx:
            self.is_initialized = True
        return 0

    # def getNextGNSSValue(self):
    #     gpsd_data = None
    #     while gpsd_data is None:
    #         gpsd_data = next(self.gnss_getter)
    #
    #     if "class" in gpsd_data and gpsd_data["class"] == "TPV" and "mode" in gpsd_data and gpsd_data["mode"] >= 2:
    #         current_gnss_data = sl.GNSSData()
    #         current_gnss_data.set_coordinates(gpsd_data["lat"], gpsd_data["lon"], gpsd_data["altMSL"], False)
    #         current_gnss_data.longitude_std = 0.001
    #         current_gnss_data.latitude_std = 0.001
    #         current_gnss_data.altitude_std = 1.0
    #
    #         gpsd_mode = gpsd_data["mode"]
    #         sl_mode = sl.GNSS_MODE.UNKNOWN
    #
    #         if gpsd_mode == 0:  # MODE_NOT_SEEN
    #             sl_mode = sl.GNSS_MODE.UNKNOWN
    #         elif gpsd_mode == 1:  # MODE_NO_FIX
    #             sl_mode = sl.GNSS_MODE.NO_FIX
    #         elif gpsd_mode == 2:  # MODE_2D
    #             sl_mode = sl.GNSS_MODE.FIX_2D
    #         elif gpsd_mode == 3:  # MODE_3D
    #             sl_mode = sl.GNSS_MODE.FIX_3D
    #
    #         sl_status = sl.GNSS_STATUS.UNKNOWN
    #         if 'status' in gpsd_data:
    #             gpsd_status = gpsd_data["status"]
    #             if gpsd_status == 0:  # STATUS_UNK
    #                 sl_status = sl.GNSS_STATUS.UNKNOWN
    #             elif gpsd_status == 1:  # STATUS_GPS
    #                 sl_status = sl.GNSS_STATUS.SINGLE
    #             elif gpsd_status == 2:  # STATUS_DGPS
    #                 sl_status = sl.GNSS_STATUS.DGNSS
    #             elif gpsd_status == 3:  # STATUS_RTK_FIX
    #                 sl_status = sl.GNSS_STATUS.RTK_FIX
    #             elif gpsd_status == 4:  # STATUS_RTK_FLT
    #                 sl_status = sl.GNSS_STATUS.RTK_FLOAT
    #             elif gpsd_status == 5:  # STATUS_DR
    #                 sl_status = sl.GNSS_STATUS.SINGLE
    #             elif gpsd_status == 6:  # STATUS_GNSSDR
    #                 sl_status = sl.GNSS_STATUS.DGNSS
    #             elif gpsd_status == 7:  # STATUS_TIME
    #                 sl_status = sl.GNSS_STATUS.UNKNOWN
    #             elif gpsd_status == 8:  # STATUS_SIM
    #                 sl_status = sl.GNSS_STATUS.UNKNOWN
    #             elif gpsd_status == 9:  # STATUS_PPS_FIX
    #                 sl_status = sl.GNSS_STATUS.SINGLE
    #
    #
    #         current_gnss_data.gnss_mode = sl_mode.value
    #         current_gnss_data.gnss_status = sl_status.value
    #
    #         position_covariance = [
    #             gpsd_data["eph"] * gpsd_data["eph"],
    #             0.0,
    #             0.0,
    #             0.0,
    #             gpsd_data["eph"] * gpsd_data["eph"],
    #             0.0,
    #             0.0,
    #             0.0,
    #             gpsd_data["epv"] * gpsd_data["epv"]
    #         ]
    #         current_gnss_data.position_covariances = position_covariance
    #         timestamp_microseconds = int(gpsd_data["time"].timestamp() * 1000000)
    #         ts = sl.Timestamp()
    #         ts.set_microseconds(timestamp_microseconds)
    #         current_gnss_data.ts = ts
    #         return current_gnss_data
    #     else:
    #         print("Fix lost : GNSS reinitialization")
    #         self.initialize()
    #         return None

    def getNextGNSSValue(self):
        while True:
            gpsd_data = next(self.gnss_getter)

            if gpsd_data.get("class") != "TPV":
                continue

            mode = gpsd_data.get("mode", 0)
            if mode < 2:
                continue

            lat = gpsd_data.get("lat")
            lon = gpsd_data.get("lon")

            alt = gpsd_data.get("altMSL")
            if alt is None:
                alt = gpsd_data.get("altHAE")
            if alt is None:
                alt = gpsd_data.get("alt")

            ts_src = gpsd_data.get("time")

            if lat is None or lon is None or alt is None or ts_src is None:
                continue

            eph = gpsd_data.get("eph")
            epv = gpsd_data.get("epv")
            # 👉 放宽（关键）
            if eph is None:
                eph = 1.0
            if epv is None:
                epv = 2.0

            # 用 GNSS 自己的真实时间戳
            gnss_time_us = int(ts_src.timestamp() * 1_000_000)

            # 同一条样本只用一次
            # if self.last_gnss_time_us is not None and gnss_time_us == self.last_gnss_time_us:
            #     continue

            eph = float(eph)
            epv = float(epv)
            eph2 = eph * eph
            epv2 = epv * epv
            cov_tuple = (round(eph2, 8), round(epv2, 8))

            # 协方差完全不变时，先跳过
            # if self.last_covariance is not None and cov_tuple == self.last_covariance:
            #     continue

            current_gnss_data = sl.GNSSData()
            current_gnss_data.set_coordinates(lat, lon, alt, False)

            current_gnss_data.longitude_std = eph
            current_gnss_data.latitude_std = eph
            current_gnss_data.altitude_std = epv

            if mode == 2:
                sl_mode = sl.GNSS_MODE.FIX_2D
            elif mode == 3:
                sl_mode = sl.GNSS_MODE.FIX_3D
            else:
                sl_mode = sl.GNSS_MODE.UNKNOWN
            current_gnss_data.gnss_mode = sl_mode.value

            gpsd_status = gpsd_data.get("status")
            if gpsd_status == 1:
                sl_status = sl.GNSS_STATUS.SINGLE
            elif gpsd_status == 2:
                sl_status = sl.GNSS_STATUS.DGNSS
            elif gpsd_status == 3:
                sl_status = sl.GNSS_STATUS.RTK_FIX
            elif gpsd_status == 4:
                sl_status = sl.GNSS_STATUS.RTK_FLOAT
            else:
                sl_status = sl.GNSS_STATUS.SINGLE
            current_gnss_data.gnss_status = sl_status.value

            current_gnss_data.position_covariances = [
                eph2, 0.0, 0.0,
                0.0, eph2, 0.0,
                0.0, 0.0, epv2
            ]

            ts = sl.Timestamp()
            ts.set_microseconds(gnss_time_us)
            current_gnss_data.ts = ts

            self.last_gnss_time_us = gnss_time_us
            self.last_covariance = cov_tuple

            print("GNSS IN:", lat, lon, "status:", gpsd_status, "ts_us:", gnss_time_us)

            return current_gnss_data

    def grab(self):
        if self.new_data:
            self.new_data = False
            return sl.ERROR_CODE.SUCCESS, self.current_gnss_data
        return sl.ERROR_CODE.FAILURE, None

    def grabGNSSData(self):
        while self.continue_to_grab:
            with self.is_initialized_mtx:
                if self.is_initialized:
                    break
            time.sleep(0.001)

        while self.continue_to_grab:
            self.current_gnss_data = self.getNextGNSSValue()
            if self.current_gnss_data is not None:
                self.new_data = True

    def stop_thread(self):
        self.continue_to_grab = False
