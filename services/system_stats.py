import os
import psutil


def get_cpu_temp():
    path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return None
    return None


def get_stats():
    return {
        "hostname": os.uname().nodename,
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "mem_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "cpu_temp": get_cpu_temp(),
    }
