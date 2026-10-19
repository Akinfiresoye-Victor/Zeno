"""
Process and network monitoring tools for system awareness.
Category: system_read
"""

from __future__ import annotations

import platform
import shutil
import socket

try:
    import psutil
except ImportError:
    psutil = None


def list_running_processes(limit: int = 15) -> list[dict]:
    """
    List top currently active system applications and processes with CPU and memory usage.

    Args:
        limit: Number of top processes to return (default 15).

    Returns:
        list[dict]: Process list with name, pid, cpu_percent, and memory_mb.
    """
    if psutil is None:
        return [{"name": "system", "pid": 1, "cpu_percent": 0.0, "memory_mb": 0.0}]

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            mem_mb = round((info["memory_info"].rss / (1024 * 1024)), 1) if info.get("memory_info") else 0.0
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "memory_mb": mem_mb,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort by memory usage descending
    processes.sort(key=lambda p: p["memory_mb"], reverse=True)
    return processes[:limit]


def get_network_status() -> dict:
    """
    Check current laptop network connectivity and interface status.

    Returns:
        dict: Hostname, local IP, internet connection status, and network IO counters.
    """
    hostname = socket.gethostname()
    local_ip = "127.0.0.1"
    internet_connected = False

    try:
        # Check local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        internet_connected = True
        s.close()
    except Exception:
        internet_connected = False

    net_io = {}
    if psutil is not None:
        try:
            counters = psutil.net_io_counters()
            net_io = {
                "bytes_sent_mb": round(counters.bytes_sent / (1024 * 1024), 1),
                "bytes_recv_mb": round(counters.bytes_recv / (1024 * 1024), 1),
            }
        except Exception:
            pass

    return {
        "hostname": hostname,
        "local_ip": local_ip,
        "internet_connected": internet_connected,
        "network_io": net_io,
    }
