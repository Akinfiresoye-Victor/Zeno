"""
System diagnostic and hardware status tools for Zeno.
Category: system_read
"""

from __future__ import annotations

from datetime import datetime
import platform
import shutil
import sys
import time

try:
    import psutil
except ImportError:
    psutil = None  # Handled gracefully if psutil is still being installed

from zeno.settings import HOME_DIR


def system_info() -> dict:
    """
    Get system telemetry including battery, CPU percent over 1 second, RAM usage,
    free disk space on home directory, uptime, operating system details, and Python version.

    Returns:
        dict: Clean numeric and formatted system details without raw objects.
    """
    # Operating system and Python versions
    os_name = platform.system()
    os_version = platform.version()
    os_release = platform.release()
    python_ver = sys.version.split()[0]

    # Battery
    battery_info = "no battery"
    if psutil is not None:
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                plugged = "plugged in" if battery.power_plugged else "unplugged"
                battery_info = f"{round(battery.percent)}% ({plugged})"
        except Exception:
            battery_info = "unavailable"

    # CPU load measured over 1 second
    cpu_percent = 0.0
    if psutil is not None:
        try:
            cpu_percent = round(psutil.cpu_percent(interval=1.0), 1)
        except Exception:
            cpu_percent = 0.0

    # RAM used and total in GB to 1 decimal place
    ram_used_gb = 0.0
    ram_total_gb = 0.0
    ram_percent = 0.0
    if psutil is not None:
        try:
            mem = psutil.virtual_memory()
            ram_used_gb = round(mem.used / (1024**3), 1)
            ram_total_gb = round(mem.total / (1024**3), 1)
            ram_percent = round(mem.percent, 1)
        except Exception:
            pass

    # Disk free space on user home folder in GB
    disk_free_gb = 0.0
    disk_total_gb = 0.0
    try:
        disk_usage = shutil.disk_usage(HOME_DIR)
        disk_free_gb = round(disk_usage.free / (1024**3), 1)
        disk_total_gb = round(disk_usage.total / (1024**3), 1)
    except Exception:
        pass

    # Uptime in hours and minutes
    uptime_hours = 0
    uptime_minutes = 0
    if psutil is not None:
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            uptime_hours = uptime_seconds // 3600
            uptime_minutes = (uptime_seconds % 3600) // 60
        except Exception:
            pass

    return {
        "os_name": os_name,
        "os_version": f"{os_release} ({os_version})",
        "python_version": python_ver,
        "battery": battery_info,
        "cpu_percent": cpu_percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_percent": ram_percent,
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "uptime": f"{uptime_hours} hours, {uptime_minutes} minutes",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
