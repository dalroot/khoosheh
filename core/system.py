"""
Hardware Metrics & System Info Provider for Khoosheh
"""
import os
import time
import shutil
import subprocess
from datetime import datetime, timezone, timedelta

def get_tehran_now():
    utc_now = datetime.now(timezone.utc)
    tehran_offset = timedelta(hours=3, minutes=30)
    tehran_time = utc_now + tehran_offset
    miladi_str = tehran_time.strftime("%Y-%m-%d %H:%M:%S")

    gy = tehran_time.year
    gm = tehran_time.month
    gd = tehran_time.day

    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = (gm > 2) and (gy + 1) or gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)

    shamsi_str = f"{jy}/{jm:02d}/{jd:02d} {tehran_time.strftime('%H:%M:%S')}"
    return {
        "shamsi": shamsi_str,
        "miladi": miladi_str,
        "combined": f"{shamsi_str} ({miladi_str})"
    }

def get_system_metrics():
    # RAM
    total_ram = 1
    used_ram = 0
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for l in lines:
            parts = l.split(":")
            if len(parts) == 2:
                mem[parts[0].strip()] = int(parts[1].split()[0])
        total_ram = mem.get("MemTotal", 1) / 1024
        avail_ram = mem.get("MemAvailable", mem.get("MemFree", 1)) / 1024
        used_ram = total_ram - avail_ram
    except Exception:
        pass

    # Disk
    du = shutil.disk_usage("/")
    total_disk = du.total / (1024**3)
    used_disk = du.used / (1024**3)

    return {
        "ram_total_mb": round(total_ram, 1),
        "ram_used_mb": round(used_ram, 1),
        "ram_percent": round((used_ram / total_ram) * 100, 1),
        "disk_total_gb": round(total_disk, 1),
        "disk_used_gb": round(used_disk, 1),
        "disk_percent": round((used_disk / total_disk) * 100, 1)
    }
