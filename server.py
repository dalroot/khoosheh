#!/usr/bin/env python3
"""
🌾 پروژه «خوشه» (Khoosheh) — نسخه ۲.۵.۰ (Universal Restore & Multi-Panel Engine)
پلتفرم هوشمند مدیریت پشتیبان‌گیری و بازگردانی چندپنله با وب‌پنل Ant Design،
موتور بازرسی عمیق دیتابیس، اسکریپت نصب یک‌خطی، احراز هویت و پشتیبانی دوگانه HTTP/HTTPS (SSL).
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import tarfile
import hashlib
import secrets
import string
import threading
import subprocess
import ssl
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler, HTTPServer

# ==================== CONSTANTS & PATHS ====================
CONFIG_FILE = "/opt/khoosheh/config.json"
BACKUP_DIR = "/var/backups/khoosheh"
SSL_DIR = "/opt/khoosheh/ssl"
CERT_FILE = os.path.join(SSL_DIR, "server.crt")
KEY_FILE = os.path.join(SSL_DIR, "server.key")
INSTALLER_PATH = "/opt/khoosheh/install.sh"
VERSION = "2.5.0 (Smart Restore & SSL)"

DEFAULT_CONFIG = {
    "bot_token": os.getenv("KHOOSHEH_BOT_TOKEN", ""),
    "admin_chat_id": int(os.getenv("KHOOSHEH_ADMIN_ID", "0")) if os.getenv("KHOOSHEH_ADMIN_ID") else 0,
    "web_port": int(os.getenv("KHOOSHEH_PORT", "2099")),
    "ssl_port": int(os.getenv("KHOOSHEH_SSL_PORT", "2098")),
    "admin_username": os.getenv("KHOOSHEH_ADMIN_USER", "admin"),
    "admin_password_hash": "",
    "auth_tokens": [],
    "backup_password": "",
    "interval_hours": 6,
    "auto_schedule": True,
    "backup_type": "full",
    "keep_local_count": 15,
    "custom_panels": [],
    "servers": [],
    "daily_digest_enabled": True,
    "daily_digest_hours": [14, 1],
    "last_backup_at": "",
    "last_status": "آماده به کار",
    "last_error": ""
}

user_states = {}
bot_lock = threading.Lock()
scheduler_stop_event = threading.Event()
bot_stop_event = threading.Event()

# ==================== CONFIG & AUTH HELPERS ====================
config_lock = threading.Lock()
_cached_config = None

def load_config():
    global _cached_config
    with config_lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(saved)
                    # Protect against accidental empty password overwrite if we had one
                    if _cached_config and _cached_config.get("admin_password_hash") and not merged.get("admin_password_hash"):
                        merged["admin_password_hash"] = _cached_config["admin_password_hash"]
                    _cached_config = dict(merged)
                    return merged
            except Exception as e:
                print(f"[Config] Error loading: {e}", file=sys.stderr)
                if _cached_config:
                    return dict(_cached_config)
        if _cached_config:
            return dict(_cached_config)
        _cached_config = dict(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    global _cached_config
    with config_lock:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        # Protect password hash from being wiped
        if _cached_config and _cached_config.get("admin_password_hash") and not cfg.get("admin_password_hash"):
            cfg["admin_password_hash"] = _cached_config["admin_password_hash"]
        _cached_config = dict(cfg)
        tmp_file = CONFIG_FILE + ".tmp." + secrets.token_hex(4)
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            os.chmod(tmp_file, 0o600)
            os.replace(tmp_file, CONFIG_FILE)
        except Exception as e:
            if os.path.exists(tmp_file):
                try: os.remove(tmp_file)
                except Exception: pass
            print(f"[Config] Error saving atomically: {e}", file=sys.stderr)

def hash_password(pwd):
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def check_token_auth(token):
    if not token:
        return False
    cfg = load_config()
    # If no password set yet, auth is not required
    if not cfg.get("admin_password_hash"):
        return True
    return token in cfg.get("auth_tokens", [])

def get_public_ip():
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        pass
    try:
        return subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()[0]
    except Exception:
        return "127.0.0.1"

# ==================== JALALI & TEHRAN TIME HELPERS ====================
def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd

def get_tehran_now():
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tehran_tz)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    shamsi_str = f"{jy:04d}/{jm:02d}/{jd:02d} {now.strftime('%H:%M:%S')}"
    miladi_str = now.strftime('%Y-%m-%d %H:%M:%S')
    return {
        "shamsi": shamsi_str,
        "miladi": miladi_str,
        "combined": f"{shamsi_str} شمسی | {miladi_str} میلادی (تهران)",
        "hour": now.hour,
        "minute": now.minute,
        "date_slot": f"{now.strftime('%Y-%m-%d')}_{now.hour:02d}"
    }

# ==================== SYSTEM METRICS ====================
def get_system_stats():
    stats = {
        "hostname": os.uname().nodename,
        "public_ip": get_public_ip(),
        "uptime": "نامشخص",
        "load": "0.00 0.00 0.00",
        "cpu_pct": 0,
        "ram_pct": 0,
        "ram_used_mb": 0,
        "ram_total_mb": 0,
        "ram_str": "",
        "disk_pct": 0,
        "disk_used": "",
        "disk_total": "",
        "disk_str": ""
    }
    try:
        with open("/proc/uptime", "r") as f:
            total_seconds = float(f.readline().split()[0])
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if days > 0:
                stats["uptime"] = f"{days} روز، {hours} ساعت"
            else:
                stats["uptime"] = f"{hours} ساعت، {minutes} دقیقه"
    except Exception:
        pass

    try:
        with open("/proc/loadavg", "r") as f:
            loads = f.readline().split()[:3]
            stats["load"] = " ".join(loads)
            stats["cpu_pct"] = min(100, int(float(loads[0]) * 100))
    except Exception:
        pass

    try:
        with open("/proc/meminfo", "r") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    mem[parts[0].strip()] = int(parts[1].split()[0])
            total = mem.get("MemTotal", 1)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            used = total - avail
            stats["ram_total_mb"] = round(total / 1024)
            stats["ram_used_mb"] = round(used / 1024)
            stats["ram_pct"] = round((used / total) * 100, 1)
            stats["ram_str"] = f"{stats['ram_used_mb']} MB / {stats['ram_total_mb']} MB"
    except Exception:
        pass

    try:
        res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=2)
        lines = res.stdout.splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            stats["disk_used"] = parts[2]
            stats["disk_total"] = parts[1]
            stats["disk_pct"] = int(parts[4].replace("%", ""))
            stats["disk_str"] = f"{parts[2]} / {parts[1]}"
    except Exception:
        pass

    return stats

# ==================== MODULAR PANEL REGISTRY ====================
class PanelRegistry:
    @staticmethod
    def detect_panels():
        panels = []
        
        # 1. 3X-UI / X-UI (Sanaei, Alireza, FranzKafkaYu, vaxilu)
        xui_candidates = [
            "/etc/x-ui/x-ui.db",
            "/usr/local/x-ui/bin/x-ui.db",
            "/usr/local/x-ui/x-ui.db",
            "/root/x-ui/x-ui.db",
            "/opt/x-ui/x-ui.db"
        ]
        xui_found = None
        for p in xui_candidates:
            if os.path.exists(p):
                xui_found = p
                break
        
        xui_svc_active = (subprocess.run(["systemctl", "is-active", "--quiet", "x-ui"]).returncode == 0)
        xui_docker_active = (subprocess.run(["docker", "ps", "-q", "-f", "name=x-ui"], capture_output=True).stdout.strip() != b"")
        if xui_found or os.path.exists("/usr/local/x-ui") or xui_svc_active or xui_docker_active:
            info = "فعال و متصل"
            if xui_found:
                try:
                    con = sqlite3.connect(xui_found)
                    c = con.execute("SELECT count(*) FROM client_traffics").fetchone()[0]
                    i = con.execute("SELECT count(*) FROM inbounds").fetchone()[0]
                    con.close()
                    info = f"فعال ({c} کاربر | {i} اینباند)"
                except Exception:
                    try:
                        con = sqlite3.connect(xui_found)
                        i = con.execute("SELECT count(*) FROM inbounds").fetchone()[0]
                        con.close()
                        info = f"فعال ({i} اینباند)"
                    except Exception:
                        pass
            panels.append({
                "id": "3x-ui",
                "name": "3X-UI / X-UI (Sanaei / Alireza / FranzKafkaYu)",
                "status": "active",
                "details": info,
                "db_type": "SQLite (Online Backup)"
            })
        else:
            panels.append({
                "id": "3x-ui",
                "name": "3X-UI / X-UI (Sanaei / Alireza / FranzKafkaYu)",
                "status": "supported",
                "details": "ماژول آماده اتصال",
                "db_type": "SQLite (Online Backup)"
            })

        # 2. PasarGuard & Pasargad Panel
        pg_candidates = [
            "/var/lib/pasarguard/db.sqlite3",
            "/opt/pasarguard/db.sqlite3"
        ]
        pg_found = None
        for p in pg_candidates:
            if os.path.exists(p):
                pg_found = p
                break
        pg_docker_active = (subprocess.run(["docker", "ps", "-q", "-f", "name=pasarguard"], capture_output=True).stdout.strip() != b"")
        if pg_found or os.path.exists("/opt/pasarguard") or pg_docker_active:
            info = "ماژول شناسایی شد"
            if pg_found:
                try:
                    con = sqlite3.connect(pg_found)
                    u_cnt = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    i_cnt = con.execute("SELECT COUNT(*) FROM inbounds").fetchone()[0]
                    n_cnt = con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
                    con.close()
                    info = f"فعال ({u_cnt} کاربر | {i_cnt} اینباند | {n_cnt} نود)"
                except Exception:
                    pass
            panels.append({"id": "pasarguard", "name": "PasarGuard (پاسارگارد)", "status": "active", "details": info, "db_type": "SQLite (Online Backup)"})
        elif os.path.exists("/opt/pasargad") or os.path.exists("/var/www/pasargad"):
            panels.append({"id": "pasargad", "name": "Pasargad Panel (پاسارگاد قدیمی)", "status": "active", "details": "ماژول شناسایی شد", "db_type": "SQLite"})
        else:
            panels.append({"id": "pasarguard", "name": "PasarGuard (پاسارگارد)", "status": "supported", "details": "ماژول آماده اتصال", "db_type": "SQLite (Online Backup)"})

        # 3. Marzban (Gozargah)
        marzban_candidates = [
            "/var/lib/marzban/db.sqlite3",
            "/opt/marzban/db.sqlite3",
            "/var/lib/marzban/marzban.db"
        ]
        marzban_found = None
        for p in marzban_candidates:
            if os.path.exists(p):
                marzban_found = p
                break
        marzban_docker_active = (subprocess.run(["docker", "ps", "-q", "-f", "name=marzban"], capture_output=True).stdout.strip() != b"")
        marzban_svc_active = (subprocess.run(["systemctl", "is-active", "--quiet", "marzban"]).returncode == 0)
        
        if marzban_found or os.path.exists("/opt/marzban") or marzban_docker_active or marzban_svc_active:
            info = "فعال و متصل"
            if marzban_found:
                try:
                    con = sqlite3.connect(marzban_found)
                    u_cnt = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    ib_cnt = con.execute("SELECT COUNT(*) FROM proxy_inbounds").fetchone()[0]
                    con.close()
                    info = f"فعال ({u_cnt} کاربر | {ib_cnt} اینباند)"
                except Exception:
                    pass
            panels.append({"id": "marzban", "name": "Marzban (مرزبان)", "status": "active", "details": info, "db_type": "SQLite/MySQL"})
        else:
            panels.append({"id": "marzban", "name": "Marzban (مرزبان)", "status": "supported", "details": "ماژول آماده اتصال", "db_type": "SQLite/MySQL"})

        # 4. Remna / Remnawave
        remna_candidates = [
            "/opt/remnawave/database.sqlite",
            "/opt/remna/database.sqlite",
            "/opt/remna/db.sqlite3",
            "/var/lib/remna/database.sqlite"
        ]
        remna_found = None
        for p in remna_candidates:
            if os.path.exists(p):
                remna_found = p
                break
        remna_dir = any(os.path.exists(d) for d in ["/opt/remnawave", "/opt/remna", "/var/lib/remna", "/opt/remnaview", "/var/www/remna"])
        remna_docker = (subprocess.run(["docker", "ps", "-q", "-f", "name=remna"], capture_output=True).stdout.strip() != b"")
        if remna_found or remna_dir or remna_docker:
            info = "ماژول شناسایی شد"
            if remna_found:
                try:
                    con = sqlite3.connect(remna_found)
                    u_cnt = con.execute("SELECT count(*) FROM users").fetchone()[0]
                    con.close()
                    info = f"فعال ({u_cnt} کاربر)"
                except Exception:
                    pass
            panels.append({"id": "remna", "name": "Remnawave / Remna (رمنا)", "status": "active", "details": info, "db_type": "SQLite/PostgreSQL"})
        else:
            panels.append({"id": "remna", "name": "Remnawave / Remna (رمنا)", "status": "supported", "details": "ماژول آماده اتصال", "db_type": "SQLite/PostgreSQL"})

        # 5. Hiddify (Manager & Config)
        hid_candidates = [
            "/opt/hiddify-config/hiddifypanel/hiddifypanel.db",
            "/opt/hiddify-manager/hiddify-panel/hiddifypanel.db",
            "/opt/hiddify-config/hiddify-panel/hiddifypanel.db"
        ]
        hid_found = None
        for p in hid_candidates:
            if os.path.exists(p):
                hid_found = p
                break
        hid_app = any(os.path.exists(d) for d in ["/opt/hiddify-manager", "/opt/hiddify-config", "/opt/hiddify-server"])
        hid_svc = (subprocess.run(["systemctl", "is-active", "--quiet", "hiddify-panel"]).returncode == 0)
        if hid_found or hid_app or hid_svc:
            info = "دیتابیس و تنظیمات پنل"
            if hid_found:
                try:
                    con = sqlite3.connect(hid_found)
                    u_cnt = con.execute("SELECT count(*) FROM user").fetchone()[0]
                    d_cnt = con.execute("SELECT count(*) FROM domain").fetchone()[0]
                    con.close()
                    info = f"فعال ({u_cnt} کاربر | {d_cnt} دامنه)"
                except Exception:
                    pass
            panels.append({"id": "hiddify", "name": "Hiddify Manager (هیدیفای)", "status": "active", "details": info, "db_type": "SQLite"})
        else:
            panels.append({"id": "hiddify", "name": "Hiddify Manager (هیدیفای)", "status": "supported", "details": "ماژول آماده اتصال", "db_type": "SQLite"})

        # 6. Network & Proxy (Hawal & Nginx & HAProxy)
        if os.path.exists("/etc/nginx") or os.path.exists("/etc/hawal") or os.path.exists("/opt/hawal") or os.path.exists("/etc/haproxy"):
            panels.append({"id": "network", "name": "Network (Nginx & Hawal Tunnels)", "status": "active", "details": "کانفیگ سابسکریپشن و تانل‌های سرور", "db_type": "Config Files"})

        cfg = load_config()
        for cp in cfg.get("custom_panels", []):
            db_p = cp.get("db_path", "")
            exists = os.path.exists(db_p)
            panels.append({
                "id": cp.get("id"),
                "name": cp.get("name"),
                "status": "custom" if exists else "missing",
                "details": f"مسیر: {db_p}" + (" (موجود)" if exists else " (یافت نشد)"),
                "db_type": cp.get("db_type", "Custom Path"),
                "is_custom": True
            })
        return panels

    @staticmethod
    def collect(staging_dir, backup_type="full"):
        collected = []
        
        # 1. 3X-UI / X-UI
        if backup_type in ["full", "3x-ui"]:
            xui_src = None
            for p in ["/etc/x-ui/x-ui.db", "/usr/local/x-ui/bin/x-ui.db", "/usr/local/x-ui/x-ui.db", "/root/x-ui/x-ui.db", "/opt/x-ui/x-ui.db"]:
                if os.path.exists(p):
                    xui_src = p
                    break
            if xui_src:
                tgt = os.path.join(staging_dir, "3x-ui")
                os.makedirs(tgt, exist_ok=True)
                db_dst = os.path.join(tgt, "x-ui.db")
                try:
                    src_conn = sqlite3.connect(xui_src)
                    try:
                        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    except Exception:
                        pass
                    dst_conn = sqlite3.connect(db_dst)
                    src_conn.backup(dst_conn, pages=-1)
                    dst_conn.close()
                    src_conn.close()
                except Exception:
                    shutil.copy2(xui_src, db_dst)

                for c_dir in ["/etc/x-ui/certs", "/root/cert", "/root/certs"]:
                    if os.path.exists(c_dir):
                        shutil.copytree(c_dir, os.path.join(tgt, "certs"), dirs_exist_ok=True)
                        break
                collected.append("3X-UI")

        # 2. Network & Proxy
        if backup_type in ["full", "network"]:
            tgt_net = os.path.join(staging_dir, "network")
            os.makedirs(tgt_net, exist_ok=True)
            has_net = False
            if os.path.exists("/etc/nginx"):
                shutil.copytree("/etc/nginx", os.path.join(tgt_net, "nginx"), dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.log"))
                has_net = True
            if os.path.exists("/opt/hawal"):
                shutil.copytree("/opt/hawal", os.path.join(tgt_net, "hawal"), dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.log", "tmp*"))
                has_net = True
            if os.path.exists("/etc/hawal"):
                shutil.copytree("/etc/hawal", os.path.join(tgt_net, "etc_hawal"), dirs_exist_ok=True)
                has_net = True
            if os.path.exists("/etc/haproxy"):
                shutil.copytree("/etc/haproxy", os.path.join(tgt_net, "haproxy"), dirs_exist_ok=True)
                has_net = True
            if has_net:
                collected.append("Network & Tunnels")

        # 3. Marzban
        if backup_type in ["full", "marzban"]:
            m_db = None
            for p in ["/var/lib/marzban/db.sqlite3", "/opt/marzban/db.sqlite3", "/var/lib/marzban/marzban.db"]:
                if os.path.exists(p):
                    m_db = p
                    break
            m_app = os.path.exists("/opt/marzban") or os.path.exists("/var/lib/marzban")
            if m_db or m_app:
                tgt_m = os.path.join(staging_dir, "marzban")
                os.makedirs(tgt_m, exist_ok=True)
                if m_db:
                    try:
                        s = sqlite3.connect(m_db)
                        try:
                            s.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        except Exception:
                            pass
                        d = sqlite3.connect(os.path.join(tgt_m, "db.sqlite3"))
                        s.backup(d)
                        d.close()
                        s.close()
                    except Exception:
                        shutil.copy2(m_db, os.path.join(tgt_m, "db.sqlite3"))
                if os.path.exists("/opt/marzban/.env"):
                    shutil.copy2("/opt/marzban/.env", os.path.join(tgt_m, ".env"))
                if os.path.exists("/opt/marzban/docker-compose.yml"):
                    shutil.copy2("/opt/marzban/docker-compose.yml", os.path.join(tgt_m, "docker-compose.yml"))
                for sub in ["xray-core", "templates", "certs"]:
                    sp = os.path.join("/var/lib/marzban", sub)
                    if os.path.exists(sp):
                        shutil.copytree(sp, os.path.join(tgt_m, sub), dirs_exist_ok=True)
                # Check for MySQL container dump if present
                try:
                    res = subprocess.run(["docker", "ps", "-q", "-f", "name=marzban.*mysql"], capture_output=True, text=True)
                    if res.stdout.strip():
                        c_id = res.stdout.strip().split()[0]
                        dump_cmd = f"docker exec {c_id} mysqldump -u root --all-databases"
                        d_res = subprocess.run(dump_cmd, shell=True, capture_output=True, text=True, timeout=30)
                        if d_res.returncode == 0 and d_res.stdout:
                            with open(os.path.join(tgt_m, "marzban_dump.sql"), "w", encoding="utf-8") as f:
                                f.write(d_res.stdout)
                except Exception:
                    pass
                collected.append("Marzban")

        # 4. PasarGuard & Pasargad
        if backup_type in ["full", "pasarguard"] and (os.path.exists("/var/lib/pasarguard/db.sqlite3") or os.path.exists("/opt/pasarguard")):
            tgt_pg = os.path.join(staging_dir, "pasarguard")
            os.makedirs(tgt_pg, exist_ok=True)
            pg_db = "/var/lib/pasarguard/db.sqlite3"
            if not os.path.exists(pg_db) and os.path.exists("/opt/pasarguard/db.sqlite3"):
                pg_db = "/opt/pasarguard/db.sqlite3"
            if os.path.exists(pg_db):
                dst_db = os.path.join(tgt_pg, "db.sqlite3")
                try:
                    src_conn = sqlite3.connect(pg_db)
                    try:
                        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    except Exception:
                        pass
                    dst_conn = sqlite3.connect(dst_db)
                    src_conn.backup(dst_conn, pages=-1)
                    dst_conn.close()
                    src_conn.close()
                except Exception:
                    shutil.copy2(pg_db, dst_db)
            if os.path.exists("/opt/pasarguard"):
                for fn in [".env", "docker-compose.yml", "sub_bridge.py"]:
                    fp = os.path.join("/opt/pasarguard", fn)
                    if os.path.exists(fp):
                        shutil.copy2(fp, os.path.join(tgt_pg, fn))
            pg_certs = "/var/lib/pasarguard/certs"
            if os.path.exists(pg_certs):
                shutil.copytree(pg_certs, os.path.join(tgt_pg, "certs"), dirs_exist_ok=True)
            node_certs = "/var/lib/pg-node/certs"
            if os.path.exists(node_certs):
                shutil.copytree(node_certs, os.path.join(tgt_pg, "node_certs"), dirs_exist_ok=True)
            collected.append("PasarGuard")

        if backup_type in ["full", "pasargad"] and os.path.exists("/opt/pasargad"):
            tgt_p = os.path.join(staging_dir, "pasargad")
            os.makedirs(tgt_p, exist_ok=True)
            shutil.copytree("/opt/pasargad", tgt_p, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.log", "cache*"))
            collected.append("Pasargad")

        # 5. Remna / Remnawave
        if backup_type in ["full", "remna"]:
            remna_dir = None
            for d in ["/opt/remnawave", "/opt/remna", "/var/lib/remna", "/opt/remnaview"]:
                if os.path.exists(d):
                    remna_dir = d
                    break
            remna_db = None
            for p in ["/opt/remnawave/database.sqlite", "/opt/remna/database.sqlite", "/opt/remna/db.sqlite3", "/var/lib/remna/database.sqlite"]:
                if os.path.exists(p):
                    remna_db = p
                    break
            if remna_dir or remna_db:
                tgt_rw = os.path.join(staging_dir, "remna")
                os.makedirs(tgt_rw, exist_ok=True)
                if remna_db:
                    try:
                        s = sqlite3.connect(remna_db)
                        try:
                            s.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        except Exception:
                            pass
                        d = sqlite3.connect(os.path.join(tgt_rw, "database.sqlite"))
                        s.backup(d)
                        d.close()
                        s.close()
                    except Exception:
                        shutil.copy2(remna_db, os.path.join(tgt_rw, "database.sqlite"))
                if remna_dir:
                    for fn in [".env", "docker-compose.yml"]:
                        fp = os.path.join(remna_dir, fn)
                        if os.path.exists(fp):
                            shutil.copy2(fp, os.path.join(tgt_rw, fn))
                    c_dir = os.path.join(remna_dir, "certs")
                    if os.path.exists(c_dir):
                        shutil.copytree(c_dir, os.path.join(tgt_rw, "certs"), dirs_exist_ok=True)
                # Check for Postgres container dump
                try:
                    res = subprocess.run(["docker", "ps", "-q", "-f", "name=remna.*db"], capture_output=True, text=True)
                    if not res.stdout.strip():
                        res = subprocess.run(["docker", "ps", "-q", "-f", "name=remnawave.*postgres"], capture_output=True, text=True)
                    if res.stdout.strip():
                        c_id = res.stdout.strip().split()[0]
                        dump_cmd = f"docker exec {c_id} pg_dumpall -U postgres"
                        d_res = subprocess.run(dump_cmd, shell=True, capture_output=True, text=True, timeout=30)
                        if d_res.returncode == 0 and d_res.stdout:
                            with open(os.path.join(tgt_rw, "remnawave.sql"), "w", encoding="utf-8") as f:
                                f.write(d_res.stdout)
                except Exception:
                    pass
                collected.append("Remna / Remnawave")

        # 6. Hiddify Manager
        if backup_type in ["full", "hiddify"]:
            hid_db = None
            for p in ["/opt/hiddify-config/hiddifypanel/hiddifypanel.db", "/opt/hiddify-manager/hiddify-panel/hiddifypanel.db", "/opt/hiddify-config/hiddify-panel/hiddifypanel.db"]:
                if os.path.exists(p):
                    hid_db = p
                    break
            hid_dir = "/opt/hiddify-manager" if os.path.exists("/opt/hiddify-manager") else ("/opt/hiddify-config" if os.path.exists("/opt/hiddify-config") else None)
            if hid_db or hid_dir:
                tgt_h = os.path.join(staging_dir, "hiddify")
                os.makedirs(tgt_h, exist_ok=True)
                if hid_db:
                    try:
                        s = sqlite3.connect(hid_db)
                        try:
                            s.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        except Exception:
                            pass
                        d = sqlite3.connect(os.path.join(tgt_h, "hiddifypanel.db"))
                        s.backup(d)
                        d.close()
                        s.close()
                    except Exception:
                        shutil.copy2(hid_db, os.path.join(tgt_h, "hiddifypanel.db"))
                if hid_dir:
                    for cf in ["current-config.json", ".env"]:
                        fp = os.path.join(hid_dir, cf)
                        if os.path.exists(fp):
                            shutil.copy2(fp, os.path.join(tgt_h, cf))
                    ssl_dir = os.path.join(hid_dir, "ssl")
                    if os.path.exists(ssl_dir):
                        shutil.copytree(ssl_dir, os.path.join(tgt_h, "ssl"), dirs_exist_ok=True)
                collected.append("Hiddify Manager")

        # Custom Panels Backup
        cfg = load_config()
        for cp in cfg.get("custom_panels", []):
            db_p = cp.get("db_path", "").strip()
            if db_p and os.path.exists(db_p):
                cid = cp.get("id", "custom_" + os.urandom(4).hex())
                tgt_c = os.path.join(staging_dir, cid)
                os.makedirs(tgt_c, exist_ok=True)
                if os.path.isfile(db_p):
                    if db_p.endswith((".db", ".sqlite", ".sqlite3")):
                        try:
                            s = sqlite3.connect(db_p)
                            d = sqlite3.connect(os.path.join(tgt_c, os.path.basename(db_p)))
                            s.backup(d)
                            d.close()
                            s.close()
                        except Exception:
                            shutil.copy2(db_p, os.path.join(tgt_c, os.path.basename(db_p)))
                    else:
                        shutil.copy2(db_p, os.path.join(tgt_c, os.path.basename(db_p)))
                elif os.path.isdir(db_p):
                    shutil.copytree(db_p, tgt_c, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.log", "tmp*", "cache*"))
                collected.append(cp.get("name", cid))
        return collected

# ==================== ARCHIVE CREATION & ENCRYPTION ====================
def generate_strong_password():
    p1 = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    p2 = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"Khoosheh-{p1}-{p2}"

def create_archive(cfg):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    staging_dir = f"/tmp/khoosheh_staging_{int(time.time())}"
    os.makedirs(staging_dir, exist_ok=True)

    btype = cfg.get("backup_type", "full")
    password = cfg.get("backup_password", "").strip()
    hostname = os.uname().nodename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"khoosheh_{hostname}_{timestamp}"

    try:
        collected = PanelRegistry.collect(staging_dir, btype)
        t_now = get_tehran_now()
        manifest = {
            "version": VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "created_at_tehran": t_now["combined"],
            "created_at_shamsi": t_now["shamsi"],
            "hostname": hostname,
            "public_ip": get_public_ip(),
            "backup_type": btype,
            "panels": collected,
            "has_encryption": bool(password)
        }
        with open(os.path.join(staging_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        tar_path = os.path.join(BACKUP_DIR, f"{base_name}.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in os.listdir(staging_dir):
                p = os.path.join(staging_dir, item)
                tar.add(p, arcname=item)

        final_path = tar_path
        is_encrypted = False

        if password:
            enc_7z = os.path.join(BACKUP_DIR, f"{base_name}.7z")
            res = subprocess.run([
                "7z", "a", f"-p{password}", "-mhe=on", enc_7z, tar_path
            ], capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and os.path.exists(enc_7z):
                final_path = enc_7z
                is_encrypted = True
                try:
                    os.remove(tar_path)
                except Exception:
                    pass

        sha = hashlib.sha256()
        with open(final_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        digest = sha.hexdigest()
        size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)

        keep = cfg.get("keep_local_count", 15)
        all_backups = sorted(
            [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("khoosheh_")],
            key=os.path.getmtime
        )
        if len(all_backups) > keep:
            for old in all_backups[:-keep]:
                try:
                    os.remove(old)
                except Exception:
                    pass

        t_now = get_tehran_now()
        cfg["last_backup_at"] = t_now["miladi"]
        cfg["last_backup_at_tehran"] = t_now["combined"]
        cfg["last_backup_at_shamsi"] = t_now["shamsi"]
        cfg["last_status"] = "موفق"
        save_config(cfg)

        return {
            "success": True,
            "filename": os.path.basename(final_path),
            "file_path": final_path,
            "size_mb": size_mb,
            "sha256": digest,
            "panels": collected,
            "is_encrypted": is_encrypted
        }
    except Exception as e:
        cfg["last_status"] = f"خطا: {str(e)[:40]}"
        save_config(cfg)
        return {"success": False, "error": str(e)}
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

# ==================== DEEP DATABASE INSPECTORS ====================
def deep_inspect_sqlite_3x_ui(db_path):
    report = {
        "found": True,
        "inbounds_count": 0,
        "protocols": [],
        "clients_count": 0,
        "total_traffic_bytes": 0,
        "total_traffic_human": "0 MB",
        "has_certs": False
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        
        if "inbounds" in tables:
            cur.execute("SELECT id, port, protocol, remark, settings FROM inbounds;")
            inbounds = cur.fetchall()
            report["inbounds_count"] = len(inbounds)
            protocols = set()
            total_clients = 0
            unique_emails = set()
            for ib in inbounds:
                if ib[2]:
                    protocols.add(str(ib[2]).upper())
                try:
                    s = json.loads(ib[4]) if ib[4] else {}
                    clients = s.get("clients", [])
                    total_clients += len(clients)
                    for c in clients:
                        em = c.get("email") or c.get("id")
                        if em:
                            unique_emails.add(em)
                except Exception:
                    pass
            report["protocols"] = sorted(list(protocols))
            report["total_client_records"] = total_clients
            report["clients_count"] = len(unique_emails) if unique_emails else total_clients

        if "client_traffics" in tables:
            cur.execute("SELECT count(distinct email), sum(up), sum(down) FROM client_traffics;")
            ct = cur.fetchone()
            if ct:
                total_bytes = (ct[1] or 0) + (ct[2] or 0)
                report["total_traffic_bytes"] = total_bytes
                if total_bytes > 1024**3:
                    report["total_traffic_human"] = f"{round(total_bytes / (1024**3), 2)} GB"
                else:
                    report["total_traffic_human"] = f"{round(total_bytes / (1024**2), 2)} MB"
                if ct[0] and not report["clients_count"]:
                    report["clients_count"] = ct[0]
        conn.close()
    except Exception as e:
        report["error"] = str(e)
    return report

def deep_inspect_sqlite_marzban(db_path):
    report = {
        "found": True,
        "users_count": 0,
        "inbounds_count": 0,
        "total_traffic_bytes": 0,
        "total_traffic_human": "0 MB"
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        if "users" in tables:
            cur.execute("SELECT count(*), sum(used_traffic) FROM users;")
            u = cur.fetchone()
            if u:
                report["users_count"] = u[0] or 0
                used = u[1] or 0
                report["total_traffic_bytes"] = used
                if used > 1024**3:
                    report["total_traffic_human"] = f"{round(used / (1024**3), 2)} GB"
                else:
                    report["total_traffic_human"] = f"{round(used / (1024**2), 2)} MB"
        if "proxy_inbounds" in tables:
            cur.execute("SELECT count(*) FROM proxy_inbounds;")
            pi = cur.fetchone()
            if pi:
                report["inbounds_count"] = pi[0] or 0
        conn.close()
    except Exception as e:
        report["error"] = str(e)
    return report

def deep_inspect_sqlite_pasarguard(db_path):
    report = {
        "found": True,
        "valid": False,
        "users_count": 0,
        "active_users": 0,
        "inbounds_count": 0,
        "nodes_count": 0,
        "total_traffic_bytes": 0,
        "total_traffic_human": "0 MB",
        "groups": []
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        if "users" in tables:
            cur.execute("SELECT count(*), sum(used_traffic) FROM users;")
            u = cur.fetchone()
            if u:
                report["users_count"] = u[0] or 0
                used = u[1] or 0
                report["total_traffic_bytes"] = used
                if used > 1024**3:
                    report["total_traffic_human"] = f"{round(used / (1024**3), 2)} GB"
                else:
                    report["total_traffic_human"] = f"{round(used / (1024**2), 2)} MB"
            try:
                cur.execute("SELECT count(*) FROM users WHERE status='active';")
                report["active_users"] = cur.fetchone()[0] or 0
            except Exception:
                report["active_users"] = report["users_count"]
        if "inbounds" in tables:
            cur.execute("SELECT count(*) FROM inbounds;")
            report["inbounds_count"] = cur.fetchone()[0] or 0
        if "nodes" in tables:
            cur.execute("SELECT count(*) FROM nodes;")
            report["nodes_count"] = cur.fetchone()[0] or 0
        if "groups" in tables:
            try:
                cur.execute("SELECT name FROM groups;")
                report["groups"] = [r[0] for r in cur.fetchall()]
            except Exception:
                pass
        report["valid"] = True
        conn.close()
    except Exception as e:
        report["error"] = str(e)
    return report

def deep_inspect_sqlite_hiddify(db_path):
    report = {
        "found": True,
        "users_count": 0,
        "domains_count": 0,
        "total_traffic_bytes": 0,
        "total_traffic_human": "0 MB",
        "domains": []
    }
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0].lower() for r in cur.fetchall()]
        for t in ["user", "users"]:
            if t in tables:
                cur.execute(f"SELECT count(*) FROM {t};")
                report["users_count"] = cur.fetchone()[0] or 0
                cur.execute(f"PRAGMA table_info({t});")
                cols = [c[1].lower() for c in cur.fetchall()]
                if "current_usage_gb" in cols:
                    cur.execute(f"SELECT sum(current_usage_gb) FROM {t};")
                    gb = cur.fetchone()[0] or 0
                    report["total_traffic_bytes"] = int(gb * 1024**3)
                    report["total_traffic_human"] = f"{round(gb, 2)} GB"
                elif "current_usage" in cols:
                    cur.execute(f"SELECT sum(current_usage) FROM {t};")
                    b = cur.fetchone()[0] or 0
                    report["total_traffic_bytes"] = b
                    report["total_traffic_human"] = f"{round(b / (1024**3), 2)} GB" if b > 1024**3 else f"{round(b / (1024**2), 2)} MB"
                break
        for t in ["domain", "domains"]:
            if t in tables:
                cur.execute(f"SELECT count(*) FROM {t};")
                report["domains_count"] = cur.fetchone()[0] or 0
                try:
                    cur.execute(f"SELECT domain FROM {t} LIMIT 5;")
                    report["domains"] = [r[0] for r in cur.fetchall()]
                except Exception:
                    pass
                break
        conn.close()
    except Exception as e:
        report["error"] = str(e)
    return report

def deep_inspect_remnawave(remna_dir):
    report = {
        "found": True,
        "users_count": 0,
        "total_traffic_bytes": 0,
        "total_traffic_human": "0 MB",
        "has_env": os.path.exists(os.path.join(remna_dir, ".env")),
        "has_compose": os.path.exists(os.path.join(remna_dir, "docker-compose.yml")),
        "has_sql": os.path.exists(os.path.join(remna_dir, "remnawave.sql")),
        "has_sqlite": False
    }
    sqlite_p = os.path.join(remna_dir, "database.sqlite")
    if not os.path.exists(sqlite_p):
        sqlite_p = os.path.join(remna_dir, "db.sqlite3")
    if os.path.exists(sqlite_p):
        report["has_sqlite"] = True
        try:
            conn = sqlite3.connect(sqlite_p)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0].lower() for r in cur.fetchall()]
            for t in ["users", "user", "clients"]:
                if t in tables:
                    cur.execute(f"SELECT count(*) FROM {t};")
                    report["users_count"] = cur.fetchone()[0] or 0
                    break
            conn.close()
        except Exception:
            pass
    elif report["has_sql"]:
        report["db_type"] = "PostgreSQL Dump"
    return report

def inspect_backup_archive(archive_path, password=""):
    staging_id = f"khoosheh_inspect_{int(time.time())}_{secrets.token_hex(4)}"
    staging_dir = os.path.join("/tmp", staging_id)
    os.makedirs(staging_dir, exist_ok=True)

    try:
        # Extract archive
        if archive_path.endswith(".7z"):
            cmd = ["7z", "x", f"-p{password}", "-y", f"-o{staging_dir}", archive_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                return {
                    "ok": False,
                    "error": "رمز عبور نادرست است یا فایل 7z معتبر نمی‌باشد." if "Wrong password" in res.stderr or "Wrong password" in res.stdout else f"خطا در استخراج فایل: {res.stderr}"
                }
            # Inside .7z there is often a tar.gz
            for item in os.listdir(staging_dir):
                if item.endswith(".tar.gz") or item.endswith(".tar"):
                    sub_tar = os.path.join(staging_dir, item)
                    with tarfile.open(sub_tar, "r:*") as tar:
                        tar.extractall(staging_dir)
                    try:
                        os.remove(sub_tar)
                    except Exception:
                        pass
        elif archive_path.endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(staging_dir)
        else:
            return {"ok": False, "error": "فرمت فایل ناشناخته است. فقط فایلهای .7z و .tar.gz پشتیبانی میشوند."}

        # 1. Read manifest.json
        manifest = {}
        manifest_file = os.path.join(staging_dir, "manifest.json")
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                pass

        # 2. Inspect 3X-UI
        xui_report = {"found": False}
        xui_db_path = os.path.join(staging_dir, "3x-ui", "x-ui.db")
        if os.path.exists(xui_db_path):
            xui_report = deep_inspect_sqlite_3x_ui(xui_db_path)
            xui_report["has_certs"] = os.path.exists(os.path.join(staging_dir, "3x-ui", "certs"))

        # 3. Inspect Marzban
        marzban_report = {"found": False}
        marzban_db_path = os.path.join(staging_dir, "marzban", "db.sqlite3")
        if os.path.exists(marzban_db_path):
            marzban_report = deep_inspect_sqlite_marzban(marzban_db_path)
            marzban_report["has_env"] = os.path.exists(os.path.join(staging_dir, "marzban", ".env"))
            marzban_report["has_compose"] = os.path.exists(os.path.join(staging_dir, "marzban", "docker-compose.yml"))
            marzban_report["has_sql"] = os.path.exists(os.path.join(staging_dir, "marzban", "marzban_dump.sql"))

        # 4. Inspect PasarGuard
        pasarguard_report = {"found": False}
        pg_db_path = os.path.join(staging_dir, "pasarguard", "db.sqlite3")
        if os.path.exists(pg_db_path):
            pasarguard_report = deep_inspect_sqlite_pasarguard(pg_db_path)
            pasarguard_report["has_env"] = os.path.exists(os.path.join(staging_dir, "pasarguard", ".env"))
            pasarguard_report["has_compose"] = os.path.exists(os.path.join(staging_dir, "pasarguard", "docker-compose.yml"))
            pasarguard_report["has_certs"] = os.path.exists(os.path.join(staging_dir, "pasarguard", "certs"))

        # 5. Inspect Remnawave
        remna_report = {"found": False}
        remna_dir = os.path.join(staging_dir, "remna")
        if os.path.exists(remna_dir):
            remna_report = deep_inspect_remnawave(remna_dir)

        # 6. Inspect Hiddify
        hiddify_report = {"found": False}
        hid_dir = os.path.join(staging_dir, "hiddify")
        hid_db_path = os.path.join(hid_dir, "hiddifypanel.db")
        if os.path.exists(hid_db_path):
            hiddify_report = deep_inspect_sqlite_hiddify(hid_db_path)
            hiddify_report["has_config"] = os.path.exists(os.path.join(hid_dir, "current-config.json"))
            hiddify_report["has_ssl"] = os.path.exists(os.path.join(hid_dir, "ssl"))
        elif os.path.exists(hid_dir):
            hiddify_report = {
                "found": True,
                "users_count": 0,
                "domains_count": 0,
                "total_traffic_human": "تنظیمات پنل",
                "has_config": os.path.exists(os.path.join(hid_dir, "current-config.json")),
                "has_ssl": os.path.exists(os.path.join(hid_dir, "ssl"))
            }

        # 7. Inspect Network
        network_report = {
            "found": os.path.exists(os.path.join(staging_dir, "network")),
            "has_nginx": os.path.exists(os.path.join(staging_dir, "network", "nginx")),
            "has_hawal": os.path.exists(os.path.join(staging_dir, "network", "hawal")) or os.path.exists(os.path.join(staging_dir, "network", "etc_hawal")),
            "has_haproxy": os.path.exists(os.path.join(staging_dir, "network", "haproxy"))
        }

        # 8. Check Target Server status
        target_state = {
            "x_ui_db_exists": os.path.exists("/etc/x-ui/x-ui.db") or os.path.exists("/usr/local/x-ui/bin/x-ui.db"),
            "x_ui_service_active": subprocess.run(["systemctl", "is-active", "--quiet", "x-ui"]).returncode == 0,
            "marzban_exists": os.path.exists("/var/lib/marzban/db.sqlite3") or os.path.exists("/opt/marzban"),
            "marzban_service_active": (subprocess.run(["systemctl", "is-active", "--quiet", "marzban"]).returncode == 0) or (subprocess.run(["docker", "ps", "-q", "-f", "name=marzban"], capture_output=True).stdout.strip() != b""),
            "pasarguard_exists": os.path.exists("/var/lib/pasarguard/db.sqlite3") or os.path.exists("/opt/pasarguard"),
            "pasarguard_service_active": (subprocess.run(["docker", "ps", "-q", "-f", "name=pasarguard"], capture_output=True).stdout.strip() != b""),
            "remna_exists": any(os.path.exists(d) for d in ["/opt/remnawave", "/opt/remna", "/var/lib/remna"]),
            "remna_service_active": (subprocess.run(["docker", "ps", "-q", "-f", "name=remna"], capture_output=True).stdout.strip() != b""),
            "hiddify_exists": any(os.path.exists(d) for d in ["/opt/hiddify-config", "/opt/hiddify-manager"]),
            "hiddify_service_active": subprocess.run(["systemctl", "is-active", "--quiet", "hiddify-panel"]).returncode == 0,
            "nginx_active": subprocess.run(["systemctl", "is-active", "--quiet", "nginx"]).returncode == 0
        }

        return {
            "ok": True,
            "staging_id": staging_id,
            "filename": os.path.basename(archive_path),
            "size_mb": round(os.path.getsize(archive_path) / (1024 * 1024), 2),
            "manifest": manifest,
            "analysis": {
                "3x-ui": xui_report,
                "marzban": marzban_report,
                "pasarguard": pasarguard_report,
                "remna": remna_report,
                "hiddify": hiddify_report,
                "network": network_report
            },
            "target_server_state": target_state
        }
    except Exception as e:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return {"ok": False, "error": f"خطا در تحلیل دیتابیس: {str(e)}"}

def execute_restore(staging_id, selected_panels, target_mode="existing", install_panel=False):
    staging_dir = os.path.join("/tmp", staging_id)
    if not os.path.exists(staging_dir):
        return {"ok": False, "error": "داده‌های استخراج‌شده موقت منقضی شده‌اند. لطفاً مجدداً فایل را انتخاب نمایید."}

    logs = []
    def log(msg, status="ok"):
        logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "status": status})

    try:
        log("آغاز عملیات بازگردانی بر روی سرور مقصد...", "info")
        ts = int(time.time())

        # 1. RESTORE 3X-UI
        if "3x-ui" in selected_panels:
            src_xui = os.path.join(staging_dir, "3x-ui")
            src_db = os.path.join(src_xui, "x-ui.db")
            if os.path.exists(src_db):
                # Safety snapshot if existing db exists
                if os.path.exists("/etc/x-ui/x-ui.db"):
                    bak_path = f"/etc/x-ui/x-ui.db.pre_restore_{ts}.bak"
                    try:
                        shutil.copy2("/etc/x-ui/x-ui.db", bak_path)
                        log(f"نسخه پشتیبان حفاظتی در مسیر {bak_path} ذخیره شد.", "ok")
                    except Exception as e:
                        log(f"هشدار در ایجاد بکاپ اضطراری: {e}", "warning")

                # Stop x-ui service before overwriting database
                log("توقف موقت سرویس x-ui جهت آزادسازی قفل‌های SQLite...", "info")
                subprocess.run(["systemctl", "stop", "x-ui"], capture_output=True)

                os.makedirs("/etc/x-ui", exist_ok=True)
                # Remove stale WAL/SHM
                for extra_ext in ["-wal", "-shm"]:
                    try:
                        if os.path.exists(f"/etc/x-ui/x-ui.db{extra_ext}"):
                            os.remove(f"/etc/x-ui/x-ui.db{extra_ext}")
                    except Exception:
                        pass
                shutil.copy2(src_db, "/etc/x-ui/x-ui.db")
                os.chmod("/etc/x-ui/x-ui.db", 0o644)
                
                # Automated Integrity Check
                try:
                    chk_con = sqlite3.connect("/etc/x-ui/x-ui.db")
                    chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                    chk_con.close()
                    if chk_res != "ok":
                        log("هشدار: دیتابیس آرشیو دارای ایراد یکپارچگی بود؛ بازگشت خودکار به نسخه امن قبلی (Rollback)...", "warning")
                        shutil.copy2(bak_path, "/etc/x-ui/x-ui.db")
                    else:
                        log("سلامت ساختار پایگاه داده تایید شد (Integrity: OK) ✅", "ok")
                except Exception as e:
                    log(f"بررسی یکپارچگی دیتابیس: {e}", "info")
                log("فایل پایگاه داده x-ui.db با موفقیت جایگزین شد و پرمیشن ۶۴۴ تنظیم گردید.", "ok")

                # Restore certs if present
                src_certs = os.path.join(src_xui, "certs")
                if os.path.exists(src_certs):
                    os.makedirs("/etc/x-ui/certs", exist_ok=True)
                    shutil.copytree(src_certs, "/etc/x-ui/certs", dirs_exist_ok=True)
                    log("سرتیفیکیت‌ها و کلیدهای امنیتی پنل در /etc/x-ui/certs بازگردانی شدند.", "ok")

                # If fresh server and install_panel is True: run 3X-UI installer
                if target_mode == "fresh" and install_panel:
                    log("در حال اجرای خودکار اسکریپت رسمی نصب 3X-UI (Sanaei)... لطفاً کمی صبر کنید.", "info")
                    inst_res = subprocess.run(
                        ["bash", "-c", "curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh | bash -s -- -y"],
                        capture_output=True, text=True, timeout=180
                    )
                    if inst_res.returncode == 0:
                        log("اسکریپت رسمی 3X-UI با موفقیت اجرا شد.", "ok")
                    else:
                        log("نصب خودکار x-ui با کد غیرصفر پایان یافت، ادامه فرایند...", "warning")

                # Start x-ui service
                log("راه‌اندازی مجدد سرویس x-ui...", "info")
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
                subprocess.run(["systemctl", "enable", "x-ui"], capture_output=True)
                subprocess.run(["systemctl", "start", "x-ui"], capture_output=True)
                time.sleep(2)

                chk = subprocess.run(["systemctl", "is-active", "x-ui"], capture_output=True, text=True)
                stat = chk.stdout.strip()
                if stat == "active":
                    log("وضعیت سرویس x-ui: فعال و پایدار (Active) ✅", "ok")
                else:
                    log(f"وضعیت سرویس x-ui: {stat} (بررسی دستی لاگ با journalctl -u x-ui)", "warning")

        # 2. RESTORE NETWORK
        if "network" in selected_panels:
            src_net = os.path.join(staging_dir, "network")
            if os.path.exists(os.path.join(src_net, "nginx")) and os.path.exists("/etc/nginx"):
                shutil.copytree(os.path.join(src_net, "nginx"), "/etc/nginx", dirs_exist_ok=True)
                subprocess.run(["systemctl", "reload", "nginx"], capture_output=True)
                log("تنظیمات Nginx بازگردانی و وب‌سرور Reload شد.", "ok")

            if os.path.exists(os.path.join(src_net, "etc_hawal")):
                os.makedirs("/etc/hawal", exist_ok=True)
                shutil.copytree(os.path.join(src_net, "etc_hawal"), "/etc/hawal", dirs_exist_ok=True)
                log("فایل‌های پیکربندی تانل هَوال در /etc/hawal بازگردانی شدند.", "ok")

        # 3. RESTORE MARZBAN
        if "marzban" in selected_panels:
            src_marzban = os.path.join(staging_dir, "marzban")
            if os.path.exists(src_marzban):
                log("آماده‌سازی بازگردانی پنل مرزبان (Marzban)...", "info")
                m_compose_path = "/opt/marzban/docker-compose.yml"
                has_compose = os.path.exists(m_compose_path)
                
                # Stop service
                if has_compose:
                    log("توقف موقت کانتینرهای مرزبان جهت آزادسازی قفل‌های دیتابیس...", "info")
                    subprocess.run(["docker", "compose", "-f", m_compose_path, "down"], capture_output=True)
                elif subprocess.run(["systemctl", "is-active", "--quiet", "marzban"]).returncode == 0:
                    log("توقف موقت سرویس systemd مرزبان...", "info")
                    subprocess.run(["systemctl", "stop", "marzban"], capture_output=True)

                # Pre-restore safety backup
                os.makedirs("/var/lib/marzban", exist_ok=True)
                os.makedirs("/opt/marzban", exist_ok=True)
                if os.path.exists("/var/lib/marzban/db.sqlite3"):
                    try:
                        shutil.copy2("/var/lib/marzban/db.sqlite3", f"/var/lib/marzban/db.sqlite3.pre_restore_{ts}.bak")
                        log("نسخه پشتیبان حفاظتی دیتابیس مرزبان ایجاد شد.", "ok")
                    except Exception:
                        pass

                # Restore SQLite DB
                src_m_db = os.path.join(src_marzban, "db.sqlite3")
                if os.path.exists(src_m_db):
                    for extra_ext in ["-wal", "-shm"]:
                        try:
                            if os.path.exists(f"/var/lib/marzban/db.sqlite3{extra_ext}"):
                                os.remove(f"/var/lib/marzban/db.sqlite3{extra_ext}")
                        except Exception:
                            pass
                    shutil.copy2(src_m_db, "/var/lib/marzban/db.sqlite3")
                    os.chmod("/var/lib/marzban/db.sqlite3", 0o644)
                    
                    # Integrity Check
                    try:
                        chk_con = sqlite3.connect("/var/lib/marzban/db.sqlite3")
                        chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                        chk_con.close()
                        if chk_res == "ok":
                            log("سلامت دیتابیس مرزبان تایید شد (Integrity: OK) ✅", "ok")
                        else:
                            log("هشدار: دیتابیس مرزبان دارای ایراد ساختاری است.", "warning")
                    except Exception as e:
                        log(f"بررسی دیتابیس مرزبان: {e}", "info")
                    log("دیتابیس مرزبان با موفقیت جایگزین شد.", "ok")

                # Restore env and compose
                for fn in [".env", "docker-compose.yml"]:
                    f_src = os.path.join(src_marzban, fn)
                    if os.path.exists(f_src):
                        shutil.copy2(f_src, os.path.join("/opt/marzban", fn))
                        log(f"فایل پیکربندی مرزبان ({fn}) بازگردانی شد.", "ok")

                # Restore xray-core and templates
                for sub in ["xray-core", "templates", "certs"]:
                    sub_src = os.path.join(src_marzban, sub)
                    if os.path.exists(sub_src):
                        shutil.copytree(sub_src, os.path.join("/var/lib/marzban", sub), dirs_exist_ok=True)

                # Restart Marzban
                if os.path.exists(m_compose_path):
                    log("راه‌اندازی کانتینرهای مرزبان با docker compose...", "info")
                    subprocess.run(["docker", "compose", "-f", m_compose_path, "up", "-d"], capture_output=True)
                    # Restore MySQL dump if present
                    src_sql = os.path.join(src_marzban, "marzban_dump.sql")
                    if os.path.exists(src_sql):
                        time.sleep(3)
                        res = subprocess.run(["docker", "ps", "-q", "-f", "name=marzban.*mysql"], capture_output=True, text=True)
                        if res.stdout.strip():
                            c_id = res.stdout.strip().split()[0]
                            with open(src_sql, "r") as sql_f:
                                subprocess.run(["docker", "exec", "-i", c_id, "mysql", "-u", "root"], stdin=sql_f, capture_output=True)
                            log("پایگاه داده MySQL مرزبان با موفقیت ایمپورت شد.", "ok")
                else:
                    subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
                    subprocess.run(["systemctl", "restart", "marzban"], capture_output=True)
                log("پنل مرزبان با موفقیت بازگردانی و راه‌اندازی شد. ✅", "ok")

        # 4. RESTORE PASARGUARD
        if "pasarguard" in selected_panels:
            src_pg = os.path.join(staging_dir, "pasarguard")
            src_db = os.path.join(src_pg, "db.sqlite3")
            if os.path.exists(src_db):
                pg_live_db = "/var/lib/pasarguard/db.sqlite3"
                if os.path.exists(pg_live_db):
                    bak_path = f"/var/lib/pasarguard/db.sqlite3.pre_restore_{ts}.bak"
                    try:
                        shutil.copy2(pg_live_db, bak_path)
                        log(f"نسخه پشتیبان حفاظتی پاسارگارد در {bak_path} ذخیره شد.", "ok")
                    except Exception as e:
                        log(f"هشدار در ایجاد بکاپ اضطراری: {e}", "warning")

                log("توقف موقت کانتینر پاسارگارد جهت آزادسازی قفل‌های SQLite...", "info")
                if os.path.exists("/opt/pasarguard/docker-compose.yml"):
                    subprocess.run(["docker", "compose", "-f", "/opt/pasarguard/docker-compose.yml", "stop"], capture_output=True)
                else:
                    subprocess.run(["docker", "stop", "pasarguard-pasarguard-1"], capture_output=True)

                os.makedirs("/var/lib/pasarguard", exist_ok=True)
                for extra_ext in ["-wal", "-shm"]:
                    try:
                        if os.path.exists(f"{pg_live_db}{extra_ext}"):
                            os.remove(f"{pg_live_db}{extra_ext}")
                    except Exception:
                        pass
                shutil.copy2(src_db, pg_live_db)
                os.chmod(pg_live_db, 0o644)

                try:
                    chk_con = sqlite3.connect(pg_live_db)
                    chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                    chk_con.close()
                    if chk_res != "ok":
                        log("هشدار: دیتابیس آرشیو دارای ایراد یکپارچگی بود؛ بازگشت به نسخه قبلی...", "warning")
                        shutil.copy2(bak_path, pg_live_db)
                    else:
                        log("سلامت پایگاه داده پاسارگارد تایید شد (Integrity: OK) ✅", "ok")
                except Exception as e:
                    log(f"بررسی سلامت دیتابیس پاسارگارد: {e}", "info")

                for fn in [".env", "docker-compose.yml", "sub_bridge.py"]:
                    src_f = os.path.join(src_pg, fn)
                    if os.path.exists(src_f):
                        os.makedirs("/opt/pasarguard", exist_ok=True)
                        shutil.copy2(src_f, os.path.join("/opt/pasarguard", fn))

                src_certs = os.path.join(src_pg, "certs")
                if os.path.exists(src_certs):
                    os.makedirs("/var/lib/pasarguard/certs", exist_ok=True)
                    shutil.copytree(src_certs, "/var/lib/pasarguard/certs", dirs_exist_ok=True)

                src_node_certs = os.path.join(src_pg, "node_certs")
                if os.path.exists(src_node_certs):
                    os.makedirs("/var/lib/pg-node/certs", exist_ok=True)
                    shutil.copytree(src_node_certs, "/var/lib/pg-node/certs", dirs_exist_ok=True)

                log("راه‌اندازی مجدد کانتینر پاسارگارد...", "info")
                if os.path.exists("/opt/pasarguard/docker-compose.yml"):
                    subprocess.run(["docker", "compose", "-f", "/opt/pasarguard/docker-compose.yml", "up", "-d"], capture_output=True)
                else:
                    subprocess.run(["docker", "start", "pasarguard-pasarguard-1"], capture_output=True)

                if subprocess.run(["systemctl", "is-active", "--quiet", "pasarguard-sub-bridge"]).returncode == 0:
                    subprocess.run(["systemctl", "restart", "pasarguard-sub-bridge"], capture_output=True)
                    log("سرویس لایو Subscription Bridge بروزرسانی شد.", "ok")

                log("پنل پاسارگارد با موفقیت بازگردانی و راه‌اندازی شد.", "ok")

        # 5. RESTORE REMNAWAVE / REMNA
        if "remna" in selected_panels:
            src_remna = os.path.join(staging_dir, "remna")
            if os.path.exists(src_remna):
                tgt_dir = "/opt/remnawave" if os.path.exists("/opt/remnawave") else "/opt/remna"
                os.makedirs(tgt_dir, exist_ok=True)
                
                # Stop containers if running
                comp_file = os.path.join(tgt_dir, "docker-compose.yml")
                if os.path.exists(comp_file):
                    log("توقف موقت کانتینرهای Remnawave...", "info")
                    subprocess.run(["docker", "compose", "-f", comp_file, "down"], capture_output=True)
                
                # Safety snapshot of .env
                if os.path.exists(os.path.join(tgt_dir, ".env")):
                    shutil.copy2(os.path.join(tgt_dir, ".env"), os.path.join(tgt_dir, f".env.pre_restore_{ts}.bak"))
                
                # Restore configs
                for fn in [".env", "docker-compose.yml"]:
                    sf = os.path.join(src_remna, fn)
                    if os.path.exists(sf):
                        shutil.copy2(sf, os.path.join(tgt_dir, fn))
                
                # Restore sqlite if present
                src_sqlite = os.path.join(src_remna, "database.sqlite")
                if os.path.exists(src_sqlite):
                    dst_sqlite = os.path.join(tgt_dir, "database.sqlite")
                    for extra_ext in ["-wal", "-shm"]:
                        try:
                            if os.path.exists(f"{dst_sqlite}{extra_ext}"):
                                os.remove(f"{dst_sqlite}{extra_ext}")
                        except Exception:
                            pass
                    shutil.copy2(src_sqlite, dst_sqlite)
                    os.chmod(dst_sqlite, 0o644)
                    try:
                        chk_con = sqlite3.connect(dst_sqlite)
                        chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                        chk_con.close()
                        if chk_res == "ok":
                            log("سلامت دیتابیس SQLite رمنا تایید شد (Integrity: OK) ✅", "ok")
                    except Exception:
                        pass
                    log("دیتابیس SQLite رمنا بازگردانی شد.", "ok")
                
                # Restore certs
                if os.path.exists(os.path.join(src_remna, "certs")):
                    shutil.copytree(os.path.join(src_remna, "certs"), os.path.join(tgt_dir, "certs"), dirs_exist_ok=True)
                
                # Bring up docker stack
                if os.path.exists(os.path.join(tgt_dir, "docker-compose.yml")):
                    log("راه‌اندازی کانتینرهای Remnawave...", "info")
                    subprocess.run(["docker", "compose", "-f", os.path.join(tgt_dir, "docker-compose.yml"), "up", "-d"], capture_output=True)
                    # Restore postgres dump if present
                    if os.path.exists(os.path.join(src_remna, "remnawave.sql")):
                        time.sleep(3)
                        res = subprocess.run(["docker", "ps", "-q", "-f", "name=remna.*db"], capture_output=True, text=True)
                        if not res.stdout.strip():
                            res = subprocess.run(["docker", "ps", "-q", "-f", "name=remnawave.*postgres"], capture_output=True, text=True)
                        if res.stdout.strip():
                            c_id = res.stdout.strip().split()[0]
                            with open(os.path.join(src_remna, "remnawave.sql"), "r") as sql_f:
                                subprocess.run(["docker", "exec", "-i", c_id, "psql", "-U", "postgres"], stdin=sql_f, capture_output=True)
                            log("دامپ دیتابیس PostgreSQL رمنا با موفقیت ایمپورت شد.", "ok")
                
                log("پنل Remnawave / Remna با موفقیت بازگردانی شد. ✅", "ok")

        # 6. RESTORE HIDDIFY MANAGER
        if "hiddify" in selected_panels:
            src_hid = os.path.join(staging_dir, "hiddify")
            if os.path.exists(src_hid):
                log("توقف موقت سرویس Hiddify جهت اعمال تنظیمات...", "info")
                subprocess.run(["systemctl", "stop", "hiddify-panel"], capture_output=True)
                
                # Target path resolution
                h_dirs = ["/opt/hiddify-config", "/opt/hiddify-manager"]
                h_target_dir = "/opt/hiddify-config"
                for hd in h_dirs:
                    if os.path.exists(hd):
                        h_target_dir = hd
                        break
                os.makedirs(h_target_dir, exist_ok=True)
                
                # Restore hiddifypanel.db
                src_db = os.path.join(src_hid, "hiddifypanel.db")
                if os.path.exists(src_db):
                    dst_db_paths = [
                        os.path.join(h_target_dir, "hiddifypanel", "hiddifypanel.db"),
                        os.path.join(h_target_dir, "hiddify-panel", "hiddifypanel.db")
                    ]
                    for dp in dst_db_paths:
                        os.makedirs(os.path.dirname(dp), exist_ok=True)
                        if os.path.exists(dp):
                            try:
                                shutil.copy2(dp, f"{dp}.pre_restore_{ts}.bak")
                            except Exception:
                                pass
                        for extra_ext in ["-wal", "-shm"]:
                            try:
                                if os.path.exists(f"{dp}{extra_ext}"):
                                    os.remove(f"{dp}{extra_ext}")
                            except Exception:
                                pass
                        shutil.copy2(src_db, dp)
                        os.chmod(dp, 0o644)
                    
                    try:
                        chk_con = sqlite3.connect(dst_db_paths[0])
                        chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                        chk_con.close()
                        if chk_res == "ok":
                            log("سلامت دیتابیس هیدیفای تایید شد (Integrity: OK) ✅", "ok")
                    except Exception:
                        pass
                    log("دیتابیس SQLite هیدیفای (hiddifypanel.db) با موفقیت بازگردانی شد.", "ok")
                
                # Restore configs and SSL
                for cf in ["current-config.json", ".env"]:
                    if os.path.exists(os.path.join(src_hid, cf)):
                        shutil.copy2(os.path.join(src_hid, cf), os.path.join(h_target_dir, cf))
                if os.path.exists(os.path.join(src_hid, "ssl")):
                    shutil.copytree(os.path.join(src_hid, "ssl"), os.path.join(h_target_dir, "ssl"), dirs_exist_ok=True)
                
                # Start service
                log("راه‌اندازی مجدد سرویس Hiddify...", "info")
                if os.path.exists(f"{h_target_dir}/apply_configs.sh"):
                    subprocess.run(["bash", f"{h_target_dir}/apply_configs.sh"], capture_output=True)
                subprocess.run(["systemctl", "restart", "hiddify-panel"], capture_output=True)
                log("پنل هیدیفای با موفقیت بازگردانی و راه‌اندازی شد. ✅", "ok")

        log("عملیات بازگردانی با موفقیت کامل انجام گردید. سیستم آماده ارائه خدمات است.", "ok")
        return {"ok": True, "logs": logs}
    except Exception as e:
        log(f"خطای بحرانی در عملیات بازگردانی: {str(e)}", "error")
        return {"ok": False, "error": str(e), "logs": logs}
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

# ==================== TELEGRAM BOT INTERACTIVE ENGINE ====================
def tg_api(method, data=None, token=None):
    if not token:
        cfg = load_config()
        token = cfg.get("bot_token")
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        body = json.dumps(data).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None

def send_document_to_telegram(chat_id, file_path, caption="", token=None):
    if not token:
        cfg = load_config()
        token = cfg.get("bot_token")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        boundary = "----WebKitFormBoundary" + secrets.token_hex(8)
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
        if caption:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend('Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
        fname = os.path.basename(file_path)
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="document"; filename="{fname}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        with open(file_path, "rb") as f:
            body.extend(f.read())
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        req = urllib.request.Request(url, data=bytes(body), headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            r = json.loads(resp.read().decode("utf-8"))
            return r.get("ok", False)
    except Exception as e:
        print(f"[Telegram Send Error] {e}", file=sys.stderr)
        return False

def get_snapshot_metrics():
    metrics = {
        'panel_type': 'سرور خام / نامشخص',
        'panel_status': 'نامشخص',
        'users_count': 0,
        'online_now': 0,
        'online_24h': 0,
        'total_traffic_gb': 0.0,
        'traffic_24h_gb': 0.0,
        'up_24h_gb': 0.0,
        'down_24h_gb': 0.0,
        'traffic_7d_gb': 0.0,
        'top_users_24h': [],
        'nodes_usage_24h': [],
        'top_users': []
    }
    # 1. Check PasarGuard
    pg_db = '/var/lib/pasarguard/db.sqlite3'
    if os.path.exists(pg_db):
        try:
            metrics['panel_type'] = 'PasarGuard'
            d_res = subprocess.run(["docker", "ps", "-f", "name=pasarguard", "--format", "{{.Status}}"], capture_output=True, text=True)
            metrics['panel_status'] = d_res.stdout.strip() or "فعال (کانتینر Docker)"

            con = sqlite3.connect(pg_db)
            cur = con.cursor()
            
            # Cumulative total
            cur.execute('SELECT count(*) FROM users;')
            metrics['users_count'] = cur.fetchone()[0] or 0
            tot = cur.execute('SELECT sum(used_traffic) FROM users;').fetchone()[0] or 0
            metrics['total_traffic_gb'] = round(tot / (1024**3), 2)

            now_utc = datetime.now(timezone.utc)
            h24 = (now_utc - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            m15 = (now_utc - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
            d7 = (now_utc - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            # Online stats
            try:
                metrics['online_now'] = cur.execute('SELECT COUNT(*) FROM users WHERE online_at >= ?', (m15,)).fetchone()[0] or 0
                metrics['online_24h'] = cur.execute('SELECT COUNT(*) FROM users WHERE online_at >= ?', (h24,)).fetchone()[0] or 0
            except Exception:
                pass

            # 24h & 7d usage from node_usages
            try:
                row_24h = cur.execute('SELECT SUM(uplink), SUM(downlink) FROM node_usages WHERE created_at >= ?', (h24,)).fetchone()
                up_24 = (row_24h[0] or 0) / (1024**3)
                down_24 = (row_24h[1] or 0) / (1024**3)
                metrics['up_24h_gb'] = round(up_24, 2)
                metrics['down_24h_gb'] = round(down_24, 2)
                metrics['traffic_24h_gb'] = round(up_24 + down_24, 2)

                row_7d = cur.execute('SELECT SUM(uplink), SUM(downlink) FROM node_usages WHERE created_at >= ?', (d7,)).fetchone()
                metrics['traffic_7d_gb'] = round(((row_7d[0] or 0) + (row_7d[1] or 0)) / (1024**3), 2)
            except Exception:
                pass

            # Top 5 users in last 24h
            try:
                top_24 = cur.execute("""
                    SELECT u.username, SUM(nu.used_traffic) as tot
                    FROM node_user_usages nu
                    JOIN users u ON u.id = nu.user_id
                    WHERE nu.created_at >= ?
                    GROUP BY u.id
                    ORDER BY tot DESC
                    LIMIT 5
                """, (h24,)).fetchall()
                for u, t in top_24:
                    metrics['top_users_24h'].append((u, round((t or 0) / (1024**3), 2)))
            except Exception:
                pass

            # Nodes usage in last 24h
            try:
                n_rows = cur.execute("""
                    SELECT n.name, SUM(nu.uplink), SUM(nu.downlink)
                    FROM node_usages nu
                    JOIN nodes n ON n.id = nu.node_id
                    WHERE nu.created_at >= ?
                    GROUP BY n.id
                """, (h24,)).fetchall()
                for name, u_up, u_down in n_rows:
                    metrics['nodes_usage_24h'].append((name, round(((u_up or 0) + (u_down or 0)) / (1024**3), 2)))
            except Exception:
                pass

            for u, traf in cur.execute('SELECT username, used_traffic FROM users ORDER BY used_traffic DESC LIMIT 5;').fetchall():
                metrics['top_users'].append((u, round((traf or 0) / (1024**3), 2)))
            con.close()
            return metrics
        except Exception as e:
            print(f"[PasarGuard Metrics Error] {e}", file=sys.stderr)

    # 2. Check 3X-UI
    db_path = '/etc/x-ui/x-ui.db'
    if os.path.exists(db_path):
        try:
            metrics['panel_type'] = '3X-UI'
            chk = subprocess.run(["systemctl", "is-active", "x-ui"], capture_output=True, text=True)
            metrics['panel_status'] = f"سرویس {chk.stdout.strip()}"
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute('SELECT count(distinct email) FROM client_traffics;')
            metrics['users_count'] = cur.fetchone()[0] or 0
            cur.execute('SELECT sum(up), sum(down) FROM client_traffics;')
            row = cur.fetchone()
            up = row[0] or 0
            down = row[1] or 0
            metrics['up_gb'] = round(up / (1024**3), 2)
            metrics['down_gb'] = round(down / (1024**3), 2)
            metrics['total_traffic_gb'] = round((up + down) / (1024**3), 2)
            cur.execute('SELECT email, (up + down) as total FROM client_traffics ORDER BY total DESC LIMIT 5;')
            for em, tot in cur.fetchall():
                metrics['top_users'].append((em, round(tot / (1024**3), 2)))
            con.close()
            return metrics
        except Exception:
            pass
    return metrics

def get_reply_keyboard():
    return {
        'keyboard': [
            [{'text': '⚡️ بکاپ فوری'}, {'text': '📊 اسنپ‌شات کاربران'}],
            [{'text': '📋 گزارش روزانه'}, {'text': '🖥 وضعیت سرور'}],
            [{'text': '📦 آخرین فایل بکاپ'}, {'text': '🌐 منوی اصلی'}]
        ],
        'resize_keyboard': True,
        'is_persistent': True
    }

def get_main_menu_data():
    cfg = load_config()
    stats = get_system_stats()
    metrics = get_snapshot_metrics()
    t_info = get_tehran_now()
    last_bk = cfg.get("last_backup_at_tehran") or cfg.get("last_backup_at") or "ثبت‌نشده"
    text = (
        '🌾 <b>سامانه مدیریت و پشتیبان‌گیری خوشه</b>\n'
        '──────────────\n'
        f'🖥 <b>سرور:</b> <code>{stats.get("hostname", "Server")}</code> (<code>{stats.get("public_ip", "-")}</code>)\n'
        f'🧠 <b>مصرف رم:</b> <code>{stats.get("ram_str", "-")} ({stats.get("ram_pct", 0)}%)</code>\n'
        f'💾 <b>دیسک:</b> <code>{stats.get("disk_str", "-")} ({stats.get("disk_pct", 0)}%)</code>\n'
        '──────────────\n'
        f'👥 <b>کاربران فعال:</b> <b>{metrics["users_count"]} کاربر</b>\n'
        f'📊 <b>مجموع مصرف ترافیک:</b> <b>{metrics["total_traffic_gb"]} GB</b>\n'
        f'⏰ <b>بازه بکاپ خودکار:</b> هر <b>{cfg.get("interval_hours", 6)}</b> ساعت\n'
        f'📅 <b>آخرین پشتیبان:</b> <code>{last_bk}</code>\n'
        f'🕐 <b>زمان فعلی (تهران):</b> <code>{t_info["shamsi"]}</code>\n'
        '──────────────\n'
        'یکی از عملیات زیر را انتخاب کنید:'
    )
    web_port = cfg.get('web_port', 2099)
    pub_ip = stats.get('public_ip', '')
    panel_url = f'http://{pub_ip}:{web_port}' if pub_ip else ''
    inline_keyboard = [
        [
            {'text': '⚡️ بکاپ فوری و ارسال فایل', 'callback_data': 'act:backup_now'},
            {'text': '📊 اسنپ‌شات مصرف', 'callback_data': 'act:snapshot'}
        ],
        [
            {'text': '📋 گزارش روزانه سیستم', 'callback_data': 'act:daily_digest'},
            {'text': '🖥 وضعیت سرور', 'callback_data': 'act:sys_stats'}
        ],
        [
            {'text': '📦 آخرین فایل بکاپ', 'callback_data': 'act:latest_file'}
        ]
    ]
    if panel_url:
        inline_keyboard.append([{'text': '🌐 ورود مستقیم به وب‌پنل', 'url': panel_url}])
    inline_keyboard.append([{'text': '🔄 بروزرسانی وضعیت', 'callback_data': 'act:refresh'}])
    keyboard = {'inline_keyboard': inline_keyboard}
    return text, keyboard

def get_node_flag(name, addr):
    n = (name + " " + addr).lower()
    if any(k in n for k in ["uk", "london", "england"]): return "🇬🇧"
    if any(k in n for k in ["nl", "amsterdam", "netherlands"]): return "🇳🇱"
    if any(k in n for k in ["de", "germany", "frankfurt"]): return "🇩🇪"
    if any(k in n for k in ["ir", "iran", "tehran"]): return "🇮🇷"
    if any(k in n for k in ["tr", "turkey", "istanbul"]): return "🇹🇷"
    if any(k in n for k in ["fr", "france", "paris"]): return "🇫🇷"
    if any(k in n for k in ["us", "usa", "america"]): return "🇺🇸"
    return "🌐"

def get_backups_24h_stats():
    now = time.time()
    cutoff_24h = now - 86400
    count_24h = 0
    total_count = 0
    latest_backup = None
    latest_size_mb = 0
    latest_mtime = 0
    if os.path.exists(BACKUP_DIR):
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("khoosheh_") and f.endswith(('.tar.gz', '.7z'))]
        total_count = len(files)
        files.sort(key=os.path.getmtime)
        for f in files:
            mtime = os.path.getmtime(f)
            if mtime >= cutoff_24h:
                count_24h += 1
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_backup = os.path.basename(f)
                try:
                    latest_size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
                except Exception:
                    pass
    return {
        "count_24h": count_24h,
        "total_count": total_count,
        "latest_backup": latest_backup,
        "latest_size_mb": latest_size_mb,
        "latest_mtime": latest_mtime
    }

def get_snapshot_text():
    metrics = get_snapshot_metrics()
    stats = get_system_stats()
    t_info = get_tehran_now()
    text = (
        '📊 <b>گزارش جامع وضعیت ترافیک و کاربران</b>\n'
        '──────────────\n'
        f'🖥 <b>سرور:</b> <code>{stats.get("hostname", "-")}</code> (<code>{stats.get("public_ip", "-")}</code>)\n'
        f'⏱ <b>آپ‌تایم سرور:</b> <code>{stats.get("uptime", "-")}</code>\n'
        f'⚡️ <b>پنل شناسایی‌شده:</b> <code>{metrics["panel_type"]}</code> [{metrics["panel_status"]}]\n'
        '──────────────\n'
        '👥 <b>وضعیت کاربران:</b>\n'
        f'├ کل کاربران ثبت‌شده: <b>{metrics["users_count"]} کاربر</b>\n'
    )
    if metrics.get('online_24h'):
        text += f'├ متصل در ۲۴ ساعت گذشته: <b>{metrics["online_24h"]} کاربر</b>\n'
    if metrics.get('online_now'):
        text += f'└ آنلاین در لحظه (۱۵ دقیقه اخیر): <b>{metrics["online_now"]} کاربر 🟢</b>\n'
    else:
        text += '└ وضعیت دیتابیس: <b>پایدار و آماده</b>\n'
    
    text += (
        '──────────────\n'
        '📈 <b>آمار ترافیک مصرفی شبکه:</b>\n\n'
    )
    if metrics.get('traffic_24h_gb') > 0:
        text += (
            f'▫️ <b>مصرف ۲۴ ساعت گذشته:</b> <b>{metrics["traffic_24h_gb"]} GB</b>\n'
            f'   ├ ⬇️ دریافت (دانلود): <b>{metrics.get("down_24h_gb", 0)} GB</b>\n'
            f'   └ ⬆️ ارسال (آپلود): <b>{metrics.get("up_24h_gb", 0)} GB</b>\n\n'
        )
    if metrics.get('traffic_7d_gb') > 0:
        text += f'▫️ <b>مصرف ۷ روز گذشته (هفته):</b> <b>{metrics["traffic_7d_gb"]} GB</b>\n\n'
    text += f'▫️ <b>مجموع کل ترافیک تاریخچه:</b> <b>{metrics["total_traffic_gb"]} GB</b>\n'

    if metrics.get('nodes_usage_24h'):
        text += '────────────────────\n🌐 <b>ترافیک نودها در ۲۴ ساعت اخیر:</b>\n\n'
        for n_name, n_tot in metrics['nodes_usage_24h']:
            text += f'• {n_name}: <b>{n_tot} GB</b>\n'

    if metrics.get('top_users_24h'):
        text += '────────────────────\n🏆 <b>۵ کاربر پرمصرف ۲۴ ساعت گذشته:</b>\n\n'
        for i, (em, tot) in enumerate(metrics['top_users_24h'], 1):
            text += f'{i}. <code>{em}</code> ── <b>{tot} GB</b>\n'
    elif metrics.get('top_users'):
        text += '────────────────────\n🏆 <b>۵ کاربر پرمصرف تاریخچه:</b>\n\n'
        for i, (em, tot) in enumerate(metrics['top_users'], 1):
            text += f'{i}. <code>{em}</code> ── <b>{tot} GB</b>\n'

    text += (
        '──────────────\n'
        f'📅 <b>زمان گزارش (تهران):</b> <code>{t_info["shamsi"]}</code>\n'
    )
    return text

def get_system_status_text():
    stats = get_system_stats()
    metrics = get_snapshot_metrics()
    t_info = get_tehran_now()
    text = (
        '🖥 <b>وضعیت منابع سرور و نودهای شبکه</b>\n'
        '──────────────\n'
        f'🏷 <b>نام هاست:</b> <code>{stats.get("hostname", "-")}</code>\n'
        f'🌐 <b>آی‌پی سرور:</b> <code>{stats.get("public_ip", "-")}</code>\n'
        f'⏱ <b>مدت زمان آپ‌تایم:</b> <code>{stats.get("uptime", "-")}</code>\n'
        f'🧠 <b>حافظه رم:</b> <code>{stats.get("ram_str", "-")} ({stats.get("ram_pct", 0)}%)</code>\n'
        f'💾 <b>فضای دیسک:</b> <code>{stats.get("disk_str", "-")} ({stats.get("disk_pct", 0)}%)</code>\n'
        f'⚡️ <b>وضعیت پنل ({metrics["panel_type"]}):</b> <code>{metrics["panel_status"]}</code>\n'
    )

    pg_db = '/var/lib/pasarguard/db.sqlite3'
    if os.path.exists(pg_db):
        try:
            con = sqlite3.connect(pg_db)
            cur = con.cursor()
            nodes = cur.execute('SELECT id, name, address, port, status, xray_version, uplink, downlink FROM nodes').fetchall()
            con.close()
            if nodes:
                text += f'────────────────────\n📡 <b>وضعیت نودهای متصل به پنل ({len(nodes)} نود):</b>\n\n'
                for id_, name, addr, port, status, xray_ver, up, down in nodes:
                    flag = get_node_flag(name, addr)
                    st_icon = "🟢 متصل" if status == "connected" else f"🔴 {status}"
                    up_gb = round((up or 0) / (1024**3), 2)
                    down_gb = round((down or 0) / (1024**3), 2)
                    tot_gb = round(((up or 0) + (down or 0)) / (1024**3), 2)
                    text += (
                        f'{flag} <b>{name}</b> [{st_icon}]\n'
                        f'├ آدرس: <code>{addr}:{port}</code>\n'
                        f'├ ترافیک کل نود: <b>{tot_gb} GB</b>\n'
                        f'├ ⬇️ دریافت (دانلود): <b>{down_gb} GB</b>\n'
                        f'├ ⬆️ ارسال (آپلود): <b>{up_gb} GB</b>\n'
                        f'└ نسخه هسته: <code>Xray {xray_ver}</code>\n\n'
                    )
        except Exception:
            pass

    xui_db = '/etc/x-ui/x-ui.db'
    if os.path.exists(xui_db):
        try:
            con = sqlite3.connect(xui_db)
            cur = con.cursor()
            inbounds = cur.execute('SELECT id, port, protocol, remark, up, down FROM inbounds').fetchall()
            con.close()
            if inbounds:
                text += f'────────────────────\n🚪 <b>اینباندهای فعال ({len(inbounds)} درگاه):</b>\n\n'
                for id_, port, proto, remark, up, down in inbounds:
                    up_gb = round((up or 0) / (1024**3), 2)
                    down_gb = round((down or 0) / (1024**3), 2)
                    tot_gb = round(((up or 0) + (down or 0)) / (1024**3), 2)
                    text += (
                        f'🚪 <b>{remark or f"Inbound {id_}"}</b> (پورت {port})\n'
                        f'├ پروتکل: <code>{proto}</code>\n'
                        f'├ ترافیک کل: <b>{tot_gb} GB</b>\n'
                        f'├ ⬇️ دریافت (دانلود): <b>{down_gb} GB</b>\n'
                        f'└ ⬆️ ارسال (آپلود): <b>{up_gb} GB</b>\n\n'
                    )
        except Exception:
            pass

    text += (
        '──────────────\n'
        f'📅 <b>زمان سرور (تهران):</b> <code>{t_info["shamsi"]}</code>\n'
        f'🌐 <b>زمان میلادی:</b> <code>{t_info["miladi"]}</code>\n'
    )
    return text

def get_live_nodes_data():
    nodes_list = []
    pg_db = '/var/lib/pasarguard/db.sqlite3'
    if os.path.exists(pg_db):
        try:
            con = sqlite3.connect(pg_db)
            cur = con.cursor()
            rows = cur.execute('SELECT id, name, address, port, status, xray_version, uplink, downlink FROM nodes').fetchall()
            con.close()
            for id_, name, addr, port, status, xray_ver, up, down in rows:
                flag = get_node_flag(name, addr)
                up_gb = round((up or 0) / (1024**3), 2)
                down_gb = round((down or 0) / (1024**3), 2)
                tot_gb = round(((up or 0) + (down or 0)) / (1024**3), 2)
                nodes_list.append({
                    "id": f"pg_{id_}",
                    "name": name,
                    "flag": flag,
                    "address": addr,
                    "port": port,
                    "status": "online" if status == "connected" else (status or "offline"),
                    "xray_version": xray_ver or "--",
                    "uplink_gb": up_gb,
                    "downlink_gb": down_gb,
                    "total_gb": tot_gb,
                    "panel": "PasarGuard"
                })
        except Exception:
            pass

    xui_db = '/etc/x-ui/x-ui.db'
    if os.path.exists(xui_db):
        try:
            con = sqlite3.connect(xui_db)
            cur = con.cursor()
            rows = cur.execute('SELECT id, port, protocol, remark, up, down FROM inbounds').fetchall()
            con.close()
            for id_, port, proto, remark, up, down in rows:
                up_gb = round((up or 0) / (1024**3), 2)
                down_gb = round((down or 0) / (1024**3), 2)
                tot_gb = round(((up or 0) + (down or 0)) / (1024**3), 2)
                nodes_list.append({
                    "id": f"xui_{id_}",
                    "name": remark or f"Inbound {id_}",
                    "flag": "🚪",
                    "address": "Local Server",
                    "port": port,
                    "status": "online",
                    "xray_version": proto,
                    "uplink_gb": up_gb,
                    "downlink_gb": down_gb,
                    "total_gb": tot_gb,
                    "panel": "3X-UI"
                })
        except Exception:
            pass

    return nodes_list

def get_daily_digest_text():
    stats = get_system_stats()
    metrics = get_snapshot_metrics()
    bk_stats = get_backups_24h_stats()
    t_info = get_tehran_now()
    cfg = load_config()

    text = (
        '📋 <b>گزارش روزانه و پایش جامع سلامت سامانه</b>\n'
        '🌾 <i>سیستم مدیریت و پشتیبان‌گیری خوشه</i>\n'
        '──────────────\n'
        f'🖥 <b>شناسه سرور:</b> <code>{stats.get("hostname", "-")}</code> (<code>{stats.get("public_ip", "-")}</code>)\n'
        f'⏱ <b>مدت زمان پایداری (Uptime):</b> <code>{stats.get("uptime", "-")}</code>\n'
        f'⚡️ <b>پنل شناسایی‌شده:</b> <code>{metrics["panel_type"]}</code> [{metrics["panel_status"]}]\n'
        '──────────────\n'
        '💾 <b>کارنامه پشتیبان‌گیری (۲۴ ساعت گذشته):</b>\n'
        f'├ 📦 تعداد بکاپ‌های موفق: <b>{bk_stats["count_24h"]} نسخه</b>\n'
        f'├ 🗄 کل بکاپ‌های محلی ذخیره: <b>{bk_stats["total_count"]} نسخه</b>\n'
        f'├ ⚖️ حجم آخرین نسخه پشتیبان: <b>{bk_stats["latest_size_mb"]} MB</b>\n'
        f'├ ⏰ دوره بکاپ خودکار: هر <b>{cfg.get("interval_hours", 6)} ساعت</b>\n'
        f'├ 📢 نوبت‌های گزارش روزانه: <b>{" و ".join([f"{int(h):02d}:00" for h in cfg.get("daily_digest_hours", [14, 1])])}</b> (تهران)\n'
        f'└ 💾 فضای دیسک سرور: <code>{stats.get("disk_str", "-")} ({stats.get("disk_pct", 0)}%)</code>\n'
        '──────────────\n'
        '🧠 <b>وضعیت منابع سخت‌افزاری:</b>\n'
        f'├ مصرف حافظه رم: <code>{stats.get("ram_str", "-")} ({stats.get("ram_pct", 0)}%)</code>\n'
        f'└ فشار پردازنده (Load): <code>{stats.get("load", "-")}</code>\n'
        '──────────────\n'
        '👥 <b>وضعیت کاربران و اتصالات:</b>\n'
        f'├ کل کاربران ثبت‌شده: <b>{metrics["users_count"]} کاربر</b>\n'
    )
    if metrics.get('online_now') is not None:
        text += f'├ آنلاین در لحظه (۱۵ دقیقه اخیر): <b>{metrics["online_now"]} کاربر 🟢</b>\n'
    if metrics.get('online_24h') is not None:
        text += f'└ کاربران فعال در ۲۴ ساعت اخیر: <b>{metrics["online_24h"]} کاربر</b>\n'
    else:
        text += '└ وضعیت پایگاه‌داده: <b>پایدار و آماده</b>\n'

    text += (
        '──────────────\n'
        '📈 <b>ترافیک مصرفی شبکه:</b>\n'
    )
    if metrics.get('traffic_24h_gb') > 0:
        text += (
            f'├ مصرف ۲۴ ساعت گذشته: <b>{metrics["traffic_24h_gb"]} GB</b>\n'
            f'│  ├ ⬇️ دریافت: <b>{metrics.get("down_24h_gb", 0)} GB</b>\n'
            f'│  └ ⬆️ ارسال: <b>{metrics.get("up_24h_gb", 0)} GB</b>\n'
        )
    if metrics.get('traffic_7d_gb') > 0:
        text += f'├ مصرف ۷ روز اخیر: <b>{metrics["traffic_7d_gb"]} GB</b>\n'
    text += f'└ مجموع مصرف تاریخچه: <b>{metrics["total_traffic_gb"]} GB</b>\n'

    pg_db = '/var/lib/pasarguard/db.sqlite3'
    if os.path.exists(pg_db):
        try:
            con = sqlite3.connect(pg_db)
            cur = con.cursor()
            nodes = cur.execute('SELECT name, address, status FROM nodes').fetchall()
            con.close()
            if nodes:
                conn_cnt = sum(1 for n in nodes if n[2] == 'connected')
                text += (
                    '──────────────\n'
                    f'📡 <b>وضعیت نودها:</b> <b>{conn_cnt} از {len(nodes)} نود متصل و فعال 🟢</b>\n'
                )
        except Exception:
            pass

    text += (
        '──────────────\n'
        f'📅 <b>زمان گزارش (تهران):</b> <code>{t_info["shamsi"]}</code>\n'
        f'🌐 <b>زمان میلادی:</b> <code>{t_info["miladi"]}</code>\n'
    )
    return text

def run_telegram_bot():
    last_update_id = 0
    print('[TelegramBot] Polling loop initialized with clean RTL UX.')
    while not bot_stop_event.is_set():
        try:
            cfg = load_config()
            token = cfg.get('bot_token')
            admin_id = cfg.get('admin_chat_id')
            if not token or not admin_id:
                time.sleep(5)
                continue
            res = tg_api('getUpdates', {'offset': last_update_id + 1, 'timeout': 20, 'allowed_updates': ['message', 'callback_query']}, token=token)
            if not res or not res.get('ok'):
                time.sleep(4)
                continue
            for upd in res.get('result', []):
                last_update_id = max(last_update_id, upd['update_id'])
                if 'message' in upd:
                    msg = upd['message']
                    chat_id = msg.get('chat', {}).get('id')
                    if str(chat_id) != str(admin_id):
                        continue
                    m_text = msg.get('text', '').strip()
                    reply_kb = get_reply_keyboard()
                    if m_text == '⚡️ بکاپ فوری':
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': '⚡️ <b>عملیات پشتیبان‌گیری آغاز شد...</b>', 'parse_mode': 'HTML'}, token=token)
                        res_b = create_archive(cfg)
                        if res_b.get('success'):
                            metrics = get_snapshot_metrics()
                            t_info = get_tehran_now()
                            hostname = os.uname().nodename
                            pub_ip = get_public_ip()
                            panels_str = " | ".join(res_b.get("panels", []))
                            enc_str = "🔐 با رمز عبور (AES-256)" if res_b.get("is_encrypted") else "🔓 بدون پسورد (.tar.gz)"
                            cap = (
                                '🌾 <b>پشتیبان جدید از سامانه خوشه</b>\n'
                                '──────────────\n'
                                f'🖥 <b>سرور:</b> <code>{hostname}</code> (<code>{pub_ip}</code>)\n'
                                f'🎯 <b>ماژول‌ها:</b> {panels_str}\n'
                                f'👥 <b>کاربران فعال:</b> <b>{metrics["users_count"]} کاربر</b>\n'
                                f'📊 <b>ترافیک مصرفی:</b> <b>{metrics["total_traffic_gb"]} GB</b>\n'
                                f'📦 <b>حجم فایل:</b> <b>{res_b["size_mb"]} MB</b>\n'
                                f'🛡 <b>حفاظت:</b> {enc_str}\n'
                                '──────────────\n'
                                f'📅 <b>زمان شمسی:</b> <code>{t_info["shamsi"]}</code>\n'
                                f'🌐 <b>زمان میلادی:</b> <code>{t_info["miladi"]} (تهران)</code>\n'
                                f'🔑 <b>هش SHA-256:</b>\n<code>{res_b.get("sha256", "")}</code>'
                            )
                            send_document_to_telegram(admin_id, res_b['file_path'], caption=cap, token=token)
                        else:
                            tg_api('sendMessage', {'chat_id': chat_id, 'text': f'❌ خطا در ساخت بکاپ: {res_b.get("error")}', 'parse_mode': 'HTML'}, token=token)
                    elif m_text.startswith(('/setdigest', '/digest_hours')):
                        parts = m_text.split()[1:]
                        new_hours = []
                        for p in parts:
                            p_clean = p.replace(':', '').replace('-', '').strip()
                            if p_clean.isdigit() and 0 <= int(p_clean) <= 23:
                                new_hours.append(int(p_clean))
                        if new_hours:
                            cfg["daily_digest_hours"] = sorted(list(set(new_hours)))
                            save_config(cfg)
                            hours_str = " و ".join([f"{h:02d}:00" for h in cfg["daily_digest_hours"]])
                            tg_api('sendMessage', {'chat_id': chat_id, 'text': f'✅ <b>ساعت‌های گزارش خودکار روزانه ذخیره شد:</b>\n⏰ نوبت‌ها: <b>{hours_str}</b> (به وقت تهران)', 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                        else:
                            tg_api('sendMessage', {'chat_id': chat_id, 'text': '⚠️ لطفاً ساعت‌ها را مشخص کنید. مثال:\n<code>/setdigest 14 1</code>', 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                    elif m_text in ['📋 گزارش روزانه', 'گزارش روزانه']:
                        digest_txt = get_daily_digest_text()
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': digest_txt, 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                    elif m_text == '📊 اسنپ‌شات کاربران':
                        snap_txt = get_snapshot_text()
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': snap_txt, 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                    elif m_text == '🖥 وضعیت سرور':
                        sys_txt = get_system_status_text()
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': sys_txt, 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                    elif m_text == '📦 آخرین فایل بکاپ':
                        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('khoosheh_') and f.endswith(('.tar.gz', '.7z'))])
                        if backups:
                            latest_p = os.path.join(BACKUP_DIR, backups[-1])
                            sz = round(os.path.getsize(latest_p) / (1024*1024), 2)
                            cap = f'📦 آخرین نسخه پشتیبان ({sz} MB)'
                            send_document_to_telegram(chat_id, latest_p, caption=cap, token=token)
                        else:
                            tg_api('sendMessage', {'chat_id': chat_id, 'text': '⚠️ هنوز فایلی ثبت نشده است.', 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                    else:
                        text, kb = get_main_menu_data()
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'reply_markup': kb}, token=token)
                        tg_api('sendMessage', {'chat_id': chat_id, 'text': '🎛 دکمه‌های پنلی برای دسترسی سریع فعال شدند:', 'parse_mode': 'HTML', 'reply_markup': reply_kb}, token=token)
                elif 'callback_query' in upd:
                    cq = upd['callback_query']
                    cid = cq.get('id')
                    from_id = cq.get('from', {}).get('id')
                    if str(from_id) != str(admin_id):
                        continue
                    data = cq.get('data', '')
                    tg_api('answerCallbackQuery', {'callback_query_id': cid}, token=token)
                    mid = cq.get('message', {}).get('message_id')
                    if data == 'act:backup_now':
                        tg_api('sendMessage', {'chat_id': admin_id, 'text': '⚡️ <b>عملیات پشتیبان‌گیری آغاز شد...</b>', 'parse_mode': 'HTML'}, token=token)
                        res_b = create_archive(cfg)
                        if res_b.get('success'):
                            metrics = get_snapshot_metrics()
                            t_info = get_tehran_now()
                            hostname = os.uname().nodename
                            pub_ip = get_public_ip()
                            panels_str = " | ".join(res_b.get("panels", []))
                            enc_str = "🔐 با رمز عبور (AES-256)" if res_b.get("is_encrypted") else "🔓 بدون پسورد (.tar.gz)"
                            cap = (
                                '🌾 <b>پشتیبان جدید از سامانه خوشه</b>\n'
                                '──────────────\n'
                                f'🖥 <b>سرور:</b> <code>{hostname}</code> (<code>{pub_ip}</code>)\n'
                                f'🎯 <b>ماژول‌ها:</b> {panels_str}\n'
                                f'👥 <b>کاربران فعال:</b> <b>{metrics["users_count"]} کاربر</b>\n'
                                f'📊 <b>ترافیک مصرفی:</b> <b>{metrics["total_traffic_gb"]} GB</b>\n'
                                f'📦 <b>حجم فایل:</b> <b>{res_b["size_mb"]} MB</b>\n'
                                f'🛡 <b>حفاظت:</b> {enc_str}\n'
                                '──────────────\n'
                                f'📅 <b>زمان شمسی:</b> <code>{t_info["shamsi"]}</code>\n'
                                f'🌐 <b>زمان میلادی:</b> <code>{t_info["miladi"]} (تهران)</code>\n'
                                f'🔑 <b>هش SHA-256:</b>\n<code>{res_b.get("sha256", "")}</code>'
                            )
                            send_document_to_telegram(admin_id, res_b['file_path'], caption=cap, token=token)
                        else:
                            tg_api('sendMessage', {'chat_id': admin_id, 'text': f'❌ خطا: {res_b.get("error")}', 'parse_mode': 'HTML'}, token=token)
                    elif data == 'act:snapshot':
                        snap_txt = get_snapshot_text()
                        tg_api('sendMessage', {'chat_id': admin_id, 'text': snap_txt, 'parse_mode': 'HTML'}, token=token)
                    elif data == 'act:daily_digest':
                        digest_txt = get_daily_digest_text()
                        tg_api('sendMessage', {'chat_id': admin_id, 'text': digest_txt, 'parse_mode': 'HTML'}, token=token)
                    elif data == 'act:sys_stats':
                        sys_txt = get_system_status_text()
                        tg_api('sendMessage', {'chat_id': admin_id, 'text': sys_txt, 'parse_mode': 'HTML'}, token=token)
                    elif data == 'act:latest_file':
                        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('khoosheh_') and f.endswith(('.tar.gz', '.7z'))])
                        if backups:
                            latest_p = os.path.join(BACKUP_DIR, backups[-1])
                            sz = round(os.path.getsize(latest_p) / (1024*1024), 2)
                            cap = f'📦 آخرین نسخه پشتیبان ({sz} MB)'
                            send_document_to_telegram(admin_id, latest_p, caption=cap, token=token)
                        else:
                            tg_api('sendMessage', {'chat_id': admin_id, 'text': '⚠️ هنوز فایلی موجود نیست.', 'parse_mode': 'HTML'}, token=token)
                    else:
                        text, kb = get_main_menu_data()
                        tg_api('editMessageText', {'chat_id': admin_id, 'message_id': mid, 'text': text, 'parse_mode': 'HTML', 'reply_markup': kb}, token=token)
        except Exception:
            time.sleep(3)

# ==================== SCHEDULER THREAD ====================
def run_scheduler():
    print("[Scheduler] Automated backup & daily digest scheduler active.")
    last_backup_check = time.time()
    
    while not scheduler_stop_event.is_set():
        try:
            cfg = load_config()
            now = time.time()
            t_info = get_tehran_now()
            token = cfg.get('bot_token')
            chat_id = cfg.get('admin_chat_id')

            # --- 1. Periodic Automated Backup ---
            if cfg.get("auto_schedule", True):
                hrs = max(cfg.get("interval_hours", 6), 1)
                interval_secs = hrs * 3600
                if now - last_backup_check >= interval_secs:
                    last_backup_check = now
                    try:
                        res = create_archive(cfg)
                        if res.get("success") and token and chat_id:
                            cap = (
                                f'🌾 <b>پشتیبان دوره‌ای خودکار خوشه</b>\n'
                                f'──────────────\n'
                                f'📦 حجم: <b>{res["size_mb"]} MB</b>\n'
                                f'📅 زمان: <code>{t_info["shamsi"]}</code>'
                            )
                            send_document_to_telegram(chat_id, res["file_path"], caption=cap, token=token)
                    except Exception as eb:
                        print(f"[Scheduler] Backup error: {eb}")

            # --- 2. Automated Daily Digest (Twice a day: 14:00 & 01:00 Tehran time) ---
            if cfg.get("daily_digest_enabled", True) and token and chat_id:
                digest_hours = cfg.get("daily_digest_hours", [14, 1])
                try:
                    digest_hours = [int(h) for h in digest_hours]
                except Exception:
                    digest_hours = [14, 1]
                cur_hour = t_info.get("hour", 0)
                cur_slot = t_info.get("date_slot", "")
                last_slot = cfg.get("last_digest_slot", "")

                if cur_hour in digest_hours and cur_slot != last_slot:
                    cfg["last_digest_slot"] = cur_slot
                    save_config(cfg)
                    try:
                        digest_txt = get_daily_digest_text()
                        reply_kb = get_reply_keyboard()
                        tg_api('sendMessage', {
                            'chat_id': chat_id,
                            'text': digest_txt,
                            'parse_mode': 'HTML',
                            'reply_markup': reply_kb
                        }, token=token)
                        print(f"[Scheduler] Automated daily digest dispatched for {cur_slot}")
                    except Exception as ed:
                        print(f"[Scheduler] Digest error: {ed}")

        except Exception as e:
            print(f"[Scheduler] General loop error: {e}")

        for _ in range(30):
            if scheduler_stop_event.is_set():
                break
            time.sleep(1)


# ==================== WEB DASHBOARD UI ====================
HTML_PAGE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>خوشه | سامانه متمرکز پشتیبان‌گیری و بازگردانی هوشمند</title>
  
  <!-- Fonts: Inter for crisp numbers + Vazirmatn for Persian text -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  
  <!-- Ant Design Reset CSS -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/antd@5/dist/reset.min.css">
  
  <!-- React & Dependencies -->
  <script src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js"></script>
  
  <!-- Ant Design v5 & Icons -->
  <script src="https://cdn.jsdelivr.net/npm/antd@5/dist/antd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@ant-design/icons@5/dist/index.umd.min.js"></script>
  
  <!-- Babel Standalone -->
  <script src="https://cdn.jsdelivr.net/npm/@babel/standalone@7.24.7/babel.min.js"></script>

  <style>
    /* ========================================================
       OFFICIAL 3X-UI COLOR SYSTEM (LIGHT & DARK)
       ======================================================== */
    :root, [data-theme="light"] {
      --bg-root: #f0f2f5;
      --bg-sidebar: #ffffff;
      --surface-card: #ffffff;
      --surface-subtle: #f8fafc;
      --surface-hover: #f1f5f9;
      --border-subtle: #e5e7eb;
      --border-hover: #cbd5e1;
      --text-primary: #111827;
      --text-secondary: #4b5563;
      --text-muted: #9ca3af;
      --primary-accent: #1677ff;
      --primary-accent-hover: #4096ff;
      --primary-accent-soft: rgba(22, 119, 255, 0.08);
      --primary-accent-border: rgba(22, 119, 255, 0.25);
      --code-bg: #f3f4f6;
      --code-border: #e5e7eb;
      --code-text: #2563eb;
      --table-header-bg: #f8fafc;
      --table-row-hover: #f1f5f9;
      --scrollbar-thumb: rgba(0, 0, 0, 0.15);
      --active-nav-bg: #e6f4ff;
      --active-nav-color: #1677ff;
      --card-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
      --baseline-color: #e5e7eb;
    }

    [data-theme="dark"] {
      --bg-root: #0b0f17;
      --bg-sidebar: #101522;
      --surface-card: #131926;
      --surface-subtle: #182030;
      --surface-hover: #1e273a;
      --border-subtle: #1e2638;
      --border-hover: #2e3a52;
      --text-primary: #f9fafb;
      --text-secondary: #9ca3af;
      --text-muted: #6b7280;
      --primary-accent: #3b82f6;
      --primary-accent-hover: #60a5fa;
      --primary-accent-soft: rgba(59, 130, 246, 0.12);
      --primary-accent-border: rgba(59, 130, 246, 0.3);
      --code-bg: #090e18;
      --code-border: #1e2638;
      --code-text: #38bdf8;
      --table-header-bg: #101522;
      --table-row-hover: rgba(255, 255, 255, 0.025);
      --scrollbar-thumb: rgba(255, 255, 255, 0.15);
      --active-nav-bg: rgba(59, 130, 246, 0.15);
      --active-nav-color: #60a5fa;
      --card-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.4);
      --baseline-color: #1e2638;
    }

    * {
      box-sizing: border-box;
      font-family: 'Vazirmatn', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* All numbers and metric labels use Inter with tabular digits */
    .num-font {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      font-variant-numeric: tabular-nums;
      direction: ltr !important;
      unicode-bidi: isolate;
    }

    html, body {
      margin: 0;
      padding: 0;
      min-height: 100%;
      background-color: var(--bg-root) !important;
      color: var(--text-primary) !important;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      transition: background-color 0.15s ease, color 0.15s ease;
    }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--primary-accent); }

    /* Shell */
    .xui-shell {
      display: flex;
      min-height: 100vh;
      width: 100%;
      background: var(--bg-root);
      direction: rtl;
    }

    /* 3X-UI Collapsible Sidebar */
    .xui-sidebar {
      background: var(--bg-sidebar);
      border-left: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      overflow-x: hidden;
      z-index: 100;
      transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      flex-shrink: 0;
    }
    .xui-sidebar.collapsed { width: 62px; }
    .xui-sidebar.expanded { width: 210px; }

    .xui-brand {
      height: 54px;
      padding: 0 13px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      gap: 12px;
      cursor: pointer;
      user-select: none;
      overflow: hidden;
    }
    .xui-logo-box {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(22, 119, 255, 0.15) 0%, rgba(16, 185, 129, 0.15) 100%);
      border: 1px solid var(--primary-accent-border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 19px;
      flex-shrink: 0;
    }
    .xui-brand-text {
      white-space: nowrap;
      overflow: hidden;
    }
    .xui-brand-title {
      font-size: 16px;
      font-weight: 800;
      color: var(--text-primary);
      line-height: 1.2;
    }
    .xui-brand-sub {
      font-size: 10.5px;
      color: var(--text-muted);
      font-family: 'Inter', monospace;
    }

    /* Nav Links */
    .xui-nav {
      padding: 10px 6px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .xui-nav-item {
      display: flex;
      align-items: center;
      height: 42px;
      border-radius: 8px;
      color: var(--text-secondary);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
      user-select: none;
    }
    .xui-sidebar.collapsed .xui-nav-item {
      justify-content: center;
      padding: 0;
    }
    .xui-sidebar.expanded .xui-nav-item {
      justify-content: space-between;
      padding: 0 14px;
    }
    .xui-nav-item:hover {
      background: var(--surface-hover);
      color: var(--text-primary);
    }
    .xui-nav-item.active {
      background: var(--active-nav-bg);
      color: var(--active-nav-color);
      font-weight: 600;
    }
    .xui-nav-icon {
      font-size: 17px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .xui-nav-label {
      white-space: nowrap;
      margin-right: 10px;
      flex: 1;
    }
    .xui-nav-badge {
      font-size: 11px;
      padding: 1px 6px;
      border-radius: 10px;
      background: var(--surface-subtle);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      font-family: 'Inter', sans-serif;
    }

    .xui-sidebar-footer {
      padding: 10px;
      border-top: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    /* Main Area */
    .xui-main {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      background: var(--bg-root);
    }

    .xui-topbar {
      height: 54px;
      padding: 0 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--surface-card);
      position: sticky;
      top: 0;
      z-index: 90;
    }
    .xui-status-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      font-weight: 600;
      color: #10b981;
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.25);
      padding: 3px 10px;
      border-radius: 16px;
    }

    .xui-body {
      padding: 20px 24px 48px;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
    }

    /* ========================================================
       3X-UI METRIC CARDS (ZERO OVERLAPPING GUARANTEED)
       Header -> Bold Stat -> AVG/PEAK -> Sparkline (at bottom)
       ======================================================== */
    .xui-card {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 8px !important;
      padding: 14px 16px 10px !important;
      box-shadow: var(--card-shadow) !important;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 142px;
      transition: all 0.15s ease !important;
    }
    .xui-card:hover {
      border-color: var(--border-hover) !important;
    }

    .xui-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }
    .xui-card-title {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.5px;
      color: var(--text-secondary);
      font-family: 'Inter', sans-serif;
      text-transform: uppercase;
    }
    .xui-card-tag {
      font-size: 11px;
      color: var(--text-muted);
      font-family: 'Inter', monospace;
      background: var(--surface-subtle);
      border: 1px solid var(--border-subtle);
      padding: 1px 6px;
      border-radius: 4px;
      direction: ltr;
    }

    .xui-card-value {
      font-size: 26px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1.1;
      margin: 2px 0;
      font-family: 'Inter', sans-serif !important;
      font-variant-numeric: tabular-nums;
      direction: ltr;
      text-align: right;
    }
    .xui-card-value small {
      font-size: 14px;
      font-weight: 500;
      color: var(--text-muted);
      margin-left: 2px;
    }

    .xui-card-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
      font-family: 'Inter', sans-serif;
      direction: ltr;
      margin-bottom: 2px;
    }

    /* Isolated sparkline box (sits strictly underneath text) */
    .xui-card-sparkline {
      width: 100%;
      height: 32px;
      margin-top: 4px;
      position: relative;
    }

    /* ========================================================
       3X-UI OVERALL SPEED CARD
       ======================================================== */
    .xui-speed-card {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 8px !important;
      padding: 16px 18px 12px !important;
      box-shadow: var(--card-shadow) !important;
    }
    .xui-speed-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
      flex-wrap: wrap;
      gap: 8px;
    }
    .xui-speed-title {
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.6px;
      color: var(--text-primary);
      font-family: 'Inter', sans-serif;
      text-transform: uppercase;
    }
    .xui-speed-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      font-family: 'Inter', sans-serif;
      margin-top: 2px;
      direction: ltr;
    }
    .xui-speed-pills {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      font-weight: 600;
      font-family: 'Inter', sans-serif;
      direction: ltr;
    }
    .xui-pill-up {
      color: #3b82f6;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .xui-pill-down {
      color: #10b981;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .xui-speed-chart {
      width: 100%;
      height: 155px;
      position: relative;
      margin: 4px 0;
    }

    .xui-speed-footer {
      display: grid;
      grid-template-columns: 1fr 1fr 1.3fr;
      gap: 12px;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--border-subtle);
      direction: ltr;
    }
    .xui-speed-col {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .xui-col-label {
      font-size: 10px;
      font-weight: 700;
      color: var(--text-muted);
      letter-spacing: 0.6px;
      text-transform: uppercase;
      font-family: 'Inter', sans-serif;
    }
    .xui-col-val {
      font-size: 15px;
      font-weight: 700;
      font-family: 'Inter', sans-serif;
      font-variant-numeric: tabular-nums;
      color: var(--text-primary);
    }
    .xui-col-val-sm {
      font-size: 12px;
      font-weight: 600;
      font-family: 'Inter', sans-serif;
      font-variant-numeric: tabular-nums;
      color: var(--text-secondary);
    }

    /* ========================================================
       3X-UI CONNECTION STATS CARD (Clean, no raw terminal)
       ======================================================== */
    .xui-conn-card {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 8px !important;
      padding: 16px 18px 14px !important;
      box-shadow: var(--card-shadow) !important;
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .xui-conn-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
    }
    .xui-conn-bigval {
      font-size: 26px;
      font-weight: 800;
      color: var(--text-primary);
      font-family: 'Inter', sans-serif;
      direction: ltr;
      margin-top: 2px;
    }
    .xui-conn-badge-blue {
      background: rgba(59, 130, 246, 0.1);
      color: #3b82f6;
      border: 1px solid rgba(59, 130, 246, 0.25);
      border-radius: 4px;
      font-size: 11px;
      padding: 1px 7px;
      font-weight: 600;
      font-family: 'Inter', sans-serif;
    }
    .xui-conn-badge-green {
      background: rgba(16, 185, 129, 0.1);
      color: #10b981;
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 4px;
      font-size: 11px;
      padding: 1px 7px;
      font-weight: 600;
      font-family: 'Inter', sans-serif;
    }

    /* Telegram Quick Action Box */
    .xui-telemetry-box {
      background: var(--surface-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 10px 12px;
      margin-top: 10px;
    }

    /* Radar Pulse */
    @keyframes radar-pulse {
      0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
      70% { transform: scale(1); box-shadow: 0 0 0 5px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .status-radar {
      display: inline-block;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
      animation: radar-pulse 2s infinite ease-in-out;
      vertical-align: middle;
    }

    .badge-slate {
      background: var(--surface-subtle) !important;
      color: var(--text-secondary) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 4px !important;
      font-size: 11px !important;
      padding: 1px 6px !important;
      font-weight: 500 !important;
      display: inline-flex !important;
      align-items: center !important;
      gap: 4px !important;
      font-family: 'Inter', sans-serif;
    }
    .badge-amber {
      background: rgba(245, 158, 11, 0.1) !important;
      color: #f59e0b !important;
      border: 1px solid rgba(245, 158, 11, 0.25) !important;
      border-radius: 4px !important;
      font-size: 11px !important;
      padding: 1px 6px !important;
      font-weight: 500 !important;
      display: inline-flex !important;
      align-items: center !important;
      gap: 4px !important;
      font-family: 'Inter', sans-serif;
    }

    .code-text {
      direction: ltr !important;
      font-family: 'Inter', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
      display: inline-block;
      font-size: 11.5px;
      background: var(--code-bg) !important;
      border: 1px solid var(--code-border) !important;
      padding: 2px 7px !important;
      border-radius: 4px !important;
      color: var(--code-text) !important;
    }

    /* Ant Design Table Overrides (3X-UI Clean Style) */
    .ant-card {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 8px !important;
      box-shadow: var(--card-shadow) !important;
      color: var(--text-primary) !important;
    }
    .ant-card-head {
      border-bottom: 1px solid var(--border-subtle) !important;
      padding: 0 16px !important;
      min-height: 44px !important;
    }
    .ant-card-head-title {
      font-size: 13.5px !important;
      font-weight: 700 !important;
      color: var(--text-primary) !important;
    }
    .ant-card-body { padding: 16px !important; }

    .ant-table-wrapper .ant-table {
      background: transparent !important;
      color: var(--text-primary) !important;
    }
    .ant-table-wrapper .ant-table-thead > tr > th {
      background: var(--table-header-bg) !important;
      border-bottom: 1px solid var(--border-subtle) !important;
      color: var(--text-secondary) !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      padding: 9px 12px !important;
      white-space: nowrap !important;
    }
    .ant-table-wrapper .ant-table-tbody > tr > td {
      border-bottom: 1px solid var(--border-subtle) !important;
      padding: 9px 12px !important;
      font-size: 13px !important;
      color: var(--text-primary) !important;
      white-space: nowrap !important;
    }
    .ant-table-wrapper .ant-table-tbody > tr:hover > td {
      background: var(--table-row-hover) !important;
    }

    .ant-btn {
      border-radius: 6px !important;
      font-size: 12.5px !important;
      font-weight: 500 !important;
      height: 32px !important;
      padding: 0 12px !important;
      box-shadow: none !important;
    }
    .ant-btn-default {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      color: var(--text-primary) !important;
    }
    .ant-btn-default:hover {
      background: var(--surface-hover) !important;
      border-color: var(--border-hover) !important;
    }
    .ant-btn-primary {
      background: var(--primary-accent) !important;
      color: #ffffff !important;
      border: none !important;
      font-weight: 600 !important;
    }
    .ant-btn-primary:hover {
      background: var(--primary-accent-hover) !important;
    }

    .ant-modal-content {
      background: var(--surface-card) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 12px !important;
      color: var(--text-primary) !important;
      padding: 22px !important;
    }
    .ant-input, .ant-input-number, .ant-select-selector {
      background: var(--surface-subtle) !important;
      border: 1px solid var(--border-subtle) !important;
      border-radius: 6px !important;
      color: var(--text-primary) !important;
    }

    @media (max-width: 860px) {
      .xui-shell { flex-direction: column; }
      .xui-sidebar {
        width: 100% !important;
        height: auto;
        position: static;
        border-left: none;
        border-bottom: 1px solid var(--border-subtle);
      }
      .xui-nav { flex-direction: row; flex-wrap: wrap; justify-content: center; }
      .xui-topbar { padding: 0 14px; }
      .xui-body { padding: 14px; }
    }
  </style>

  <script>
    window.onerror = function(msg, url, lineNo, colNo, error) {
      console.error('UI Crash:', msg, error);
      var root = document.getElementById('root');
      if (root && (!root.children.length || !root.querySelector('.xui-shell'))) {
        root.innerHTML = '<div style="direction:rtl;padding:50px;text-align:center;font-family:sans-serif;color:#ff4d4f;background:#f0f2f5;height:100vh;">' +
          '<h2 style="color:#ff4d4f;">خطا در بارگذاری سامانه خوشه</h2>' +
          '<p style="color:#1e293b;font-family:monospace;background:#ffffff;padding:12px 20px;border-radius:6px;display:inline-block;direction:ltr;border:1px solid #e5e7eb;">' +
          msg + (lineNo ? ' (سطر: ' + lineNo + ')' : '') + '</p>' +
          '<br><br><button onclick="location.reload()" style="padding:10px 24px;border:none;border-radius:6px;background:#1677ff;color:#fff;cursor:pointer;font-weight:bold;">بارگذاری مجدد</button>' +
          '</div>';
      }
      return false;
    };
  </script>
</head>
<body>
  <div id="root">
    <div style="display:flex;height:100vh;align-items:center;justify-content:center;background:#f0f2f5;color:#111827;direction:rtl;font-family:sans-serif;">
      <div style="text-align:center;">
        <div style="font-size:42px;margin-bottom:16px;">🌾</div>
        <div style="font-size:18px;font-weight:700;margin-bottom:8px;">سامانه خوشه (Khoosheh)</div>
        <div style="font-size:13px;color:#6b7280;">در حال بارگذاری محیط ۳X-UI...</div>
      </div>
    </div>
  </div>

  <script type="text/babel">
    const {
      ConfigProvider, App, Layout, Menu, Card, Row, Col, Statistic,
      Table, Button, Form, Input, InputNumber, Select, Tag, Space,
      Badge, Typography, Divider, Switch, Modal, Popconfirm, Progress, Radio, Tooltip,
      Steps, Upload, Alert, Timeline, Checkbox
    } = antd;
    const { Text } = Typography;

    // Icons with safe fallbacks
    const icons = window.icons || {};
    const DashboardOutlined = icons.DashboardOutlined || (() => <span>📊</span>);
    const ClusterOutlined = icons.ClusterOutlined || (() => <span>🖥</span>);
    const AppstoreOutlined = icons.AppstoreOutlined || (() => <span>🧩</span>);
    const SettingOutlined = icons.SettingOutlined || (() => <span>⚙️</span>);
    const CloudDownloadOutlined = icons.CloudDownloadOutlined || (() => <span>📦</span>);
    const ThunderboltOutlined = icons.ThunderboltOutlined || (() => <span>⚡️</span>);
    const ReloadOutlined = icons.ReloadOutlined || (() => <span>🔄</span>);
    const PlusOutlined = icons.PlusOutlined || (() => <span>➕</span>);
    const DeleteOutlined = icons.DeleteOutlined || (() => <span>🗑</span>);
    const SendOutlined = icons.SendOutlined || (() => <span>📡</span>);
    const SaveOutlined = icons.SaveOutlined || (() => <span>💾</span>);
    const DownloadOutlined = icons.DownloadOutlined || (() => <span>⬇️</span>);
    const CheckCircleOutlined = icons.CheckCircleOutlined || (() => <span>✅</span>);
    const HddOutlined = icons.HddOutlined || (() => <span>💾</span>);
    const SyncOutlined = icons.SyncOutlined || (() => <span>🔄</span>);
    const LockOutlined = icons.LockOutlined || (() => <span>🔒</span>);
    const UserOutlined = icons.UserOutlined || (() => <span>👤</span>);
    const KeyOutlined = icons.KeyOutlined || (() => <span>🔑</span>);
    const CopyOutlined = icons.CopyOutlined || (() => <span>📋</span>);
    const SafetyCertificateOutlined = icons.SafetyCertificateOutlined || (() => <span>🛡</span>);
    const InboxOutlined = icons.InboxOutlined || (() => <span>📥</span>);
    const ArrowRightOutlined = icons.ArrowRightOutlined || (() => <span>➔</span>);
    const ArrowLeftOutlined = icons.ArrowLeftOutlined || (() => <span>⬅</span>);
    const MenuFoldOutlined = icons.MenuFoldOutlined || (() => <span>◀</span>);
    const MenuUnfoldOutlined = icons.MenuUnfoldOutlined || (() => <span>▶</span>);
    const LogoutOutlined = icons.LogoutOutlined || (() => <span>🚪</span>);

    const PRESETS = [
      { id: '3x-ui', name: '3X-UI (Sanaei / Alireza)', desc: 'دیتابیس کاربران و کانفیگ‌ها', default_path: '/etc/x-ui/x-ui.db', type: 'sqlite' },
      { id: 'marzban', name: 'مرزبان (Marzban)', desc: 'دیتابیس SQLite و فایل‌های محیطی .env', default_path: '/var/lib/marzban/db.sqlite3', type: 'sqlite' },
      { id: 'pasarguard', name: 'پاسارگارد (PasarGuard)', desc: 'دیتابیس SQLite کاربران و کانتینر پنل', default_path: '/var/lib/pasarguard/db.sqlite3', type: 'sqlite' },
      { id: 'remna', name: 'رمنا / رمناویو (Remna / RemnaView)', desc: 'دیتابیس کاربران و لاگ‌ها', default_path: '/opt/remna/database.sqlite', type: 'sqlite' },
      { id: 'hiddify', name: 'هیدیفای منیجر (Hiddify Manager)', desc: 'دیتابیس اصلی و سرتیفیکیت‌ها', default_path: '/opt/hiddify-manager/hiddify-panel/hiddifypanel.db', type: 'sqlite' },
      { id: 'network', name: 'شبکه و تانل‌ها (Nginx & Hawal)', desc: 'فایل‌های تانل و کانفیگ‌های وب‌سرور', default_path: '/etc/hawal/agent.json', type: 'config' },
      { id: 'custom', name: 'سایر / مسیر دلخواه', desc: 'مسیر اختصاصی فایل دیتابیس یا پوشه', default_path: '', type: 'custom' },
    ];

    const KhooshehApp = ({ themeMode, toggleTheme }) => {
      const { message, notification } = App.useApp();
      const [currentTab, setCurrentTab] = React.useState('overview');
      const [collapsed, setCollapsed] = React.useState(false);
      const [data, setData] = React.useState(null);
      const [loading, setLoading] = React.useState(true);
      const [actionLoading, setActionLoading] = React.useState(false);
      const [addPanelModal, setAddPanelModal] = React.useState(false);
      const [selectedPreset, setSelectedPreset] = React.useState('3x-ui');
      const [digestModal, setDigestModal] = React.useState(false);

      // Authentication State
      const [authStatus, setAuthStatus] = React.useState({ setup_required: false, authenticated: true });
      const [setupModal, setSetupModal] = React.useState(false);
      const [loginModal, setLoginModal] = React.useState(false);

      // Restore Wizard State
      const [restoreStep, setRestoreStep] = React.useState(0);
      const [restoreSourceType, setRestoreSourceType] = React.useState('existing');
      const [selectedBackupFile, setSelectedBackupFile] = React.useState('');
      const [restorePassword, setRestorePassword] = React.useState('');
      const [uploadedFilename, setUploadedFilename] = React.useState('');
      const [inspectLoading, setInspectLoading] = React.useState(false);
      const [inspectResult, setInspectResult] = React.useState(null);
      const [selectedPanelsToRestore, setSelectedPanelsToRestore] = React.useState(['3x-ui']);
      const [targetServerMode, setTargetServerMode] = React.useState('existing');
      const [installPanelOnFresh, setInstallPanelOnFresh] = React.useState(true);
      const [executeLoading, setExecuteLoading] = React.useState(false);
      const [restoreLogs, setRestoreLogs] = React.useState([]);
      const [restoreCompleted, setRestoreCompleted] = React.useState(false);

      const [form] = Form.useForm();
      const [panelForm] = Form.useForm();
      const [setupForm] = Form.useForm();
      const [loginForm] = Form.useForm();

      const getAuthHeader = () => {
        const token = localStorage.getItem('khoosheh_auth_token');
        return token ? { 'X-Khoosheh-Token': token } : {};
      };

      const checkAuth = async () => {
        try {
          const res = await fetch('/api/auth/status', { headers: getAuthHeader() });
          const json = await res.json();
          setAuthStatus(json);
          if (json.setup_required) {
            setSetupModal(true);
          } else if (!json.authenticated) {
            setLoginModal(true);
          }
        } catch (e) {
          console.error(e);
        }
      };

      const fetchData = async (silent = false) => {
        if (!silent) setLoading(true);
        try {
          const res = await fetch('/api/status', { headers: getAuthHeader() });
          const json = await res.json();
          if (json.ok) {
            setData(json);
            if (json.backups && json.backups.length > 0 && !selectedBackupFile) {
              setSelectedBackupFile(json.backups[0].filename);
            }
            form.setFieldsValue({
              bot_token: json.config.bot_token || '',
              admin_chat_id: json.config.admin_chat_id || '',
              backup_password: json.config.backup_password || '',
              interval_hours: json.config.interval_hours || 6,
              daily_digest_enabled: json.config.daily_digest_enabled !== false,
              daily_digest_hours: json.config.daily_digest_hours || [14, 1]
            });
          }
        } catch (e) {
          if (!silent) message.error('خطا در دریافت وضعیت سرور');
        } finally {
          if (!silent) setLoading(false);
        }
      };

      React.useEffect(() => {
        checkAuth();
        fetchData();
        const timer = setInterval(() => fetchData(true), 30000);
        return () => clearInterval(timer);
      }, []);

      // Handlers
      const handleGenerateSetupPassword = () => {
        const p1 = Math.random().toString(36).substring(2, 6).toUpperCase();
        const p2 = Math.random().toString(36).substring(2, 6).toLowerCase();
        const num = Math.floor(1000 + Math.random() * 9000);
        const pwd = `Khoosheh#${p1}${num}${p2}!`;
        setupForm.setFieldValue('password', pwd);
        setupForm.setFieldValue('confirm_password', pwd);
        message.info('رمز عبور فوق‌امن تصادفی تولید و درج شد.');
      };

      const handleSaveSetup = async (values) => {
        if (values.password !== values.confirm_password) {
          message.error('تکرار کلمه عبور با کلمه عبور واردشده مطابقت ندارد.');
          return;
        }
        setActionLoading(true);
        try {
          const res = await fetch('/api/auth/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: values.username || 'admin', password: values.password })
          });
          const json = await res.json();
          if (json.ok) {
            localStorage.setItem('khoosheh_auth_token', json.token);
            message.success('راه‌اندازی امنیتی با موفقیت ثبت شد و وارد سیستم شدید.');
            setSetupModal(false);
            checkAuth();
            fetchData();
          } else {
            message.error(json.error || 'خطا در ثبت اطلاعات.');
          }
        } catch (e) {
          message.error('خطا در اتصال به سرور');
        } finally {
          setActionLoading(false);
        }
      };

      const handleLogin = async (values) => {
        setActionLoading(true);
        try {
          const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(values)
          });
          const json = await res.json();
          if (json.ok) {
            localStorage.setItem('khoosheh_auth_token', json.token);
            message.success('ورود موفقیت‌آمیز بود.');
            setLoginModal(false);
            checkAuth();
            fetchData();
          } else {
            message.error(json.error || 'نام کاربری یا رمز عبور اشتباه است.');
          }
        } catch (e) {
          message.error('خطا در ارتباط با سرور');
        } finally {
          setActionLoading(false);
        }
      };

      const handleLogout = () => {
        localStorage.removeItem('khoosheh_auth_token');
        message.info('شما از سامانه خارج شدید.');
        setLoginModal(true);
      };

      const handleStartInspect = async () => {
        const targetFile = restoreSourceType === 'upload' ? uploadedFilename : selectedBackupFile;
        if (!targetFile) {
          message.warning('لطفاً یک فایل پشتیبان انتخاب یا آپلود نمایید.');
          return;
        }
        setInspectLoading(true);
        try {
          const res = await fetch('/api/restore/inspect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({ filename: targetFile, password: restorePassword })
          });
          const json = await res.json();
          if (json.ok) {
            setInspectResult(json);
            const panelsFound = [];
            if (json.analysis['pasarguard']?.found) panelsFound.push('pasarguard');
            if (json.analysis['3x-ui']?.found) panelsFound.push('3x-ui');
            if (json.analysis['marzban']?.found) panelsFound.push('marzban');
            if (json.analysis['remna']?.found) panelsFound.push('remna');
            if (json.analysis['hiddify']?.found) panelsFound.push('hiddify');
            if (json.analysis['network']?.found) panelsFound.push('network');
            setSelectedPanelsToRestore(panelsFound.length > 0 ? panelsFound : ['3x-ui']);
            
            if (!json.target_server_state.x_ui_db_exists) {
              setTargetServerMode('fresh');
            } else {
              setTargetServerMode('existing');
            }
            
            setRestoreStep(1);
            message.success('آرشیو با موفقیت رمزگشایی و متادیتای دیتابیس تحلیل شد.');
          } else {
            notification.error({
              message: 'خطا در تحلیل فایل پشتیبان',
              description: json.error || 'رمز عبور نادرست است یا ساختار فایل آسیب دیده است.'
            });
          }
        } catch (e) {
          message.error('خطا در ارتباط با سرور.');
        } finally {
          setInspectLoading(false);
        }
      };

      const handleExecuteRestore = async () => {
        if (!inspectResult || !inspectResult.staging_id) {
          message.error('داده‌های استخراج‌شده در دسترس نیست. مجدداً آنالیز را انجام دهید.');
          return;
        }
        setExecuteLoading(true);
        setRestoreStep(3);
        try {
          const res = await fetch('/api/restore/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({
              staging_id: inspectResult.staging_id,
              selected_panels: selectedPanelsToRestore,
              target_mode: targetServerMode,
              install_panel: targetServerMode === 'fresh' && installPanelOnFresh
            })
          });
          const json = await res.json();
          setRestoreLogs(json.logs || []);
          if (json.ok) {
            setRestoreCompleted(true);
            notification.success({
              message: 'بازگردانی با موفقیت به پایان رسید 🎉',
              description: 'پایگاه‌های داده جایگزین شدند، مجوزها تنظیم و سرویس‌های هدف با موفقیت راه‌اندازی گردیدند.'
            });
            fetchData(true);
          } else {
            notification.error({
              message: 'خطا در اجرای بازگردانی',
              description: json.error || 'مشکلی در اعمال داده‌ها رخ داد.'
            });
          }
        } catch (e) {
          message.error('خطا در ارتباط با سرور.');
        } finally {
          setExecuteLoading(false);
        }
      };

      const handleTriggerBackup = async () => {
        setActionLoading(true);
        try {
          const res = await fetch('/api/backup', { method: 'POST', headers: getAuthHeader() });
          const json = await res.json();
          if (json.ok) {
            message.success(`آرشیو پشتیبان ساخته و تحویل داده شد: ${json.filename}`);
            fetchData(true);
          } else {
            message.error('خطا در ایجاد پشتیبان');
          }
        } catch (e) {
          message.error('خطا در اتصال به سرور');
        } finally {
          setActionLoading(false);
        }
      };

      const handleSendDigest = async () => {
        setActionLoading(true);
        try {
          const res = await fetch('/api/send_digest', { method: 'POST', headers: getAuthHeader() });
          const json = await res.json();
          if (json.ok) {
            notification.success({
              message: 'گزارش به تلگرام مخابره شد',
              description: 'کارنامه سلامت سیستم و کاربران به ادمین ارسال گردید.'
            });
          } else {
            notification.error({
              message: 'خطا در ارسال گزارش',
              description: json.error || 'ارتباط با تلگرام برقرار نشد.'
            });
          }
        } catch (e) {
          message.error('خطا در فراخوانی سرویس تلگرام');
        } finally {
          setActionLoading(false);
        }
      };

      const handleSaveSettings = async (values) => {
        setActionLoading(true);
        try {
          const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify(values)
          });
          const json = await res.json();
          if (json.ok) {
            message.success('تنظیمات با موفقیت ذخیره شد.');
            fetchData(true);
          } else {
            message.error('خطا در ذخیره تنظیمات');
          }
        } catch (e) {
          message.error('خطا در برقراری ارتباط');
        } finally {
          setActionLoading(false);
        }
      };

      const handleTestBot = async () => {
        setActionLoading(true);
        try {
          const res = await fetch('/api/test_bot', { method: 'POST', headers: getAuthHeader() });
          const json = await res.json();
          if (json.ok) {
            notification.success({
              message: 'اتصال ربات تلگرام پایدار است',
              description: 'پیام تستی با موفقیت به چت ادمین مخابره شد.'
            });
          } else {
            notification.error({
              message: 'خطا در ارتباط تلگرام',
              description: json.error || 'توکن یا شناسه ادمین نامعتبر است.'
            });
          }
        } catch (e) {
          message.error('خطا در تست اتصال');
        } finally {
          setActionLoading(false);
        }
      };

      const handlePresetChange = (presetId) => {
        setSelectedPreset(presetId);
        const p = PRESETS.find(x => x.id === presetId);
        if (p) {
          panelForm.setFieldsValue({
            type: p.id,
            name: p.name,
            db_path: p.default_path,
            details: p.desc
          });
        }
      };

      const handleAddPanel = async (values) => {
        try {
          const res = await fetch('/api/panels/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify(values)
          });
          const json = await res.json();
          if (json.ok) {
            message.success('پنل جدید با موفقیت به چرخه پشتیبان‌گیری افزوده شد.');
            setAddPanelModal(false);
            panelForm.resetFields();
            fetchData(true);
          } else {
            message.error(json.error || 'خطا در ثبت پنل');
          }
        } catch (e) {
          message.error('خطا در ثبت پنل');
        }
      };

      const handleDeletePanel = async (id) => {
        try {
          const res = await fetch('/api/panels/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({ id })
          });
          const json = await res.json();
          if (json.ok) {
            message.success('پنل با موفقیت حذف شد.');
            fetchData(true);
          }
        } catch (e) {
          message.error('خطا در حذف پنل');
        }
      };

      const handleCopyInstaller = () => {
        const ip = data?.stats?.public_ip || window.location.hostname;
        const cmd = `curl -sSL http://${ip}:2099/install.sh | bash`;
        navigator.clipboard.writeText(cmd);
        message.success('دستور یک‌خطی نصب در حافظه کپی شد: ' + cmd);
      };

      // 3X-UI Clean Tables
      const backupColumns = [
        {
          title: 'نام فایل آرشیو',
          dataIndex: 'filename',
          key: 'filename',
          render: (text) => (
            <Space size={8}>
              {text.endsWith('.7z') ? <span className="badge-amber">AES-256</span> : <span className="badge-slate">tar.gz</span>}
              <Text code className="code-text num-font">{text}</Text>
            </Space>
          )
        },
        {
          title: 'زمان ایجاد',
          dataIndex: 'date_str',
          key: 'date_str',
          width: 170,
          render: (text) => <Text type="secondary" className="num-font" style={{ fontSize: 12 }}>{text}</Text>
        },
        {
          title: 'حجم',
          dataIndex: 'size_mb',
          key: 'size_mb',
          width: 100,
          render: (val) => <Text strong className="num-font" style={{ color: '#10b981' }}>{val} MB</Text>
        },
        {
          title: 'هش SHA-256',
          dataIndex: 'sha256',
          key: 'sha256',
          width: 170,
          render: (text) => (
            <Text copyable code className="code-text num-font" style={{ fontSize: 11 }}>
              {text ? `${text.substring(0, 14)}...` : '--'}
            </Text>
          )
        },
        {
          title: 'عملیات',
          key: 'action',
          width: 170,
          align: 'center',
          render: (_, record) => (
            <Space size={6}>
              <Button
                type="primary"
                ghost
                size="small"
                icon={<DownloadOutlined />}
                href={`/download/${record.filename}`}
                target="_blank"
              >
                دانلود
              </Button>
              <Button
                size="small"
                icon={<SyncOutlined />}
                onClick={() => {
                  setSelectedBackupFile(record.filename);
                  setRestoreSourceType('existing');
                  setCurrentTab('restore');
                  setRestoreStep(0);
                }}
              >
                بازگردانی
              </Button>
            </Space>
          )
        }
      ];

      const panelColumns = [
        {
          title: 'عنوان پنل',
          dataIndex: 'name',
          key: 'name',
          render: (text, record) => (
            <Space size={8}>
              <Text strong>{text}</Text>
              {record.is_custom && <span className="badge-slate">سفارشی</span>}
            </Space>
          )
        },
        {
          title: 'وضعیت',
          dataIndex: 'status',
          key: 'status',
          width: 120,
          render: (s) => (s === 'active' || s === 'custom') ? <span className="badge-emerald" style={{ color: '#10b981' }}>🟢 متصل</span> : <span className="badge-slate">آماده</span>
        },
        {
          title: 'نوع دیتابیس',
          dataIndex: 'db_type',
          key: 'db_type',
          width: 180,
          render: (t) => <Text code className="code-text num-font">{t}</Text>
        },
        {
          title: 'توضیحات و مسیر فایل',
          dataIndex: 'details',
          key: 'details',
          render: (text) => <Text type="secondary" className="num-font">{text}</Text>
        },
        {
          title: 'عملیات',
          key: 'action',
          width: 90,
          align: 'center',
          render: (_, record) => record.is_custom ? (
            <Popconfirm title="آیا این پنل از لیست حذف شود؟" onConfirm={() => handleDeletePanel(record.id)} okText="بله" cancelText="خیر">
              <Button type="text" danger size="small" icon={<DeleteOutlined />}>حذف</Button>
            </Popconfirm>
          ) : <Text type="secondary">-</Text>
        }
      ];

      const serverColumns = [
        {
          title: 'کشور',
          dataIndex: 'country',
          key: 'country',
          width: 140,
          render: (c) => <span className="badge-slate">{c}</span>
        },
        {
          title: 'نام نود سرور',
          dataIndex: 'name',
          key: 'name',
          render: (text) => <Text strong>{text}</Text>
        },
        {
          title: 'آدرس آی‌پی (IPv4)',
          dataIndex: 'ip',
          key: 'ip',
          width: 160,
          render: (ip) => <Text code className="code-text num-font" style={{ color: '#10b981' }}>{ip}</Text>
        },
        {
          title: 'نقش در زیرساخت',
          dataIndex: 'role',
          key: 'role'
        },
        {
          title: 'وضعیت',
          dataIndex: 'status',
          key: 'status',
          width: 110,
          render: () => <span className="badge-emerald" style={{ color: '#10b981' }}><span className="status-radar" style={{ margin: 0, marginLeft: 4 }}></span>آنلاین</span>
        },
        {
          title: 'سرویس‌ها و پورت‌ها',
          dataIndex: 'details',
          key: 'details',
          render: (d) => <Text type="secondary">{d}</Text>
        }
      ];

      const liveNodeColumns = [
        {
          title: 'کشور',
          dataIndex: 'flag',
          key: 'flag',
          width: 80,
          align: 'center',
          render: (f) => <span style={{ fontSize: 18 }}>{f || '🌐'}</span>
        },
        {
          title: 'نام نود',
          dataIndex: 'name',
          key: 'name',
          render: (text) => <Text strong>{text}</Text>
        },
        {
          title: 'آدرس و پورت اتصال',
          key: 'address',
          render: (_, r) => <Text code className="code-text num-font" style={{ color: '#38bdf8' }}>{r.address}:{r.port}</Text>
        },
        {
          title: 'وضعیت اتصال',
          dataIndex: 'status',
          key: 'status',
          width: 120,
          render: (st) => st === 'online' ? <span className="badge-emerald" style={{ color: '#10b981' }}><span className="status-radar" style={{ margin: 0, marginLeft: 4 }}></span>متصل</span> : <span style={{ color: '#ef4444' }}>{st || 'قطع'}</span>
        },
        {
          title: 'هسته (Core)',
          dataIndex: 'xray_version',
          key: 'xray_version',
          render: (v) => <span className="badge-slate num-font">Xray {v}</span>
        },
        {
          title: 'دریافت (دانلود)',
          dataIndex: 'downlink_gb',
          key: 'downlink_gb',
          render: (d) => <span className="num-font" style={{ color: '#10b981' }}>↓ {d} GB</span>
        },
        {
          title: 'ارسال (آپلود)',
          dataIndex: 'uplink_gb',
          key: 'uplink_gb',
          render: (u) => <span className="num-font" style={{ color: '#f59e0b' }}>↑ {u} GB</span>
        },
        {
          title: 'ترافیک کل نود',
          dataIndex: 'total_gb',
          key: 'total_gb',
          render: (t) => <Text strong className="num-font">{t} GB</Text>
        }
      ];

      const stats = data?.stats || {};
      const cfg = data?.config || {};
      const hostIp = stats.public_ip || window.location.hostname;

      const navItems = [
        { key: 'overview', icon: <DashboardOutlined />, label: 'داشبورد مدیریتی' },
        { key: 'backups', icon: <CloudDownloadOutlined />, label: 'آرشیوهای پشتیبان', badge: data?.backups?.length },
        { key: 'restore', icon: <SyncOutlined />, label: 'بازیابی هوشمند' },
        { key: 'panels', icon: <AppstoreOutlined />, label: 'پایگاه‌های داده' },
        { key: 'servers', icon: <ClusterOutlined />, label: 'نودها و سرورها', badge: data?.live_nodes?.length },
        { key: 'settings', icon: <SettingOutlined />, label: 'تنظیمات و ربات' },
      ];

      return (
        <div className="xui-shell">
          {/* 3X-UI COLLAPSIBLE SIDEBAR */}
          <aside className={`xui-sidebar ${collapsed ? 'collapsed' : 'expanded'}`}>
            <div>
              {/* BRAND / LOGO */}
              <div className="xui-brand" onClick={() => setCollapsed(!collapsed)} title={collapsed ? 'باز کردن منو' : 'بستن منو'}>
                <div className="xui-logo-box">🌾</div>
                {!collapsed && (
                  <div className="xui-brand-text">
                    <div className="xui-brand-title">خـوشـــه</div>
                    <div className="xui-brand-sub">KHOOSHEH v{data?.version || '2.5'}</div>
                  </div>
                )}
              </div>

              {/* NAV MENU */}
              <nav className="xui-nav">
                {navItems.map((item) => {
                  const content = (
                    <div
                      key={item.key}
                      className={`xui-nav-item ${currentTab === item.key ? 'active' : ''}`}
                      onClick={() => setCurrentTab(item.key)}
                    >
                      <span className="xui-nav-icon">{item.icon}</span>
                      {!collapsed && <span className="xui-nav-label">{item.label}</span>}
                      {!collapsed && item.badge !== undefined && item.badge > 0 && (
                        <span className="xui-nav-badge">{item.badge}</span>
                      )}
                    </div>
                  );
                  return collapsed ? (
                    <Tooltip placement="left" title={item.label} key={item.key}>
                      {content}
                    </Tooltip>
                  ) : content;
                })}
              </nav>
            </div>

            {/* SIDEBAR FOOTER */}
            <div className="xui-sidebar-footer">
              {!collapsed ? (
                <>
                  <div style={{ background: 'var(--surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 8px', fontSize: 11 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-muted)' }}>IP:</span>
                      <span
                        className="code-text num-font"
                        style={{ cursor: 'pointer', fontSize: 10.5 }}
                        onClick={() => {
                          navigator.clipboard.writeText(hostIp);
                          message.success('آدرس IP کپی شد');
                        }}
                      >
                        {hostIp}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ color: 'var(--text-muted)' }}>پوسته:</span>
                      <Switch
                        checkedChildren="🌙"
                        unCheckedChildren="☀️"
                        checked={themeMode === 'dark'}
                        onChange={toggleTheme}
                        size="small"
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                    <Button
                      block
                      size="small"
                      icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                      onClick={() => setCollapsed(!collapsed)}
                    >
                      بستن
                    </Button>
                    {authStatus.authenticated && !authStatus.setup_required && (
                      <Button danger size="small" icon={<LogoutOutlined />} onClick={handleLogout} />
                    )}
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <Tooltip placement="left" title={themeMode === 'dark' ? 'تم روشن' : 'تم تاریک'}>
                    <Button
                      type="text"
                      size="small"
                      onClick={() => toggleTheme(themeMode !== 'dark')}
                      style={{ fontSize: 16 }}
                    >
                      {themeMode === 'dark' ? '🌙' : '☀️'}
                    </Button>
                  </Tooltip>
                  <Tooltip placement="left" title="باز کردن منو">
                    <Button
                      type="text"
                      size="small"
                      icon={<MenuUnfoldOutlined />}
                      onClick={() => setCollapsed(false)}
                    />
                  </Tooltip>
                  {authStatus.authenticated && !authStatus.setup_required && (
                    <Tooltip placement="left" title="خروج">
                      <Button type="text" danger size="small" icon={<LogoutOutlined />} onClick={handleLogout} />
                    </Tooltip>
                  )}
                </div>
              )}
            </div>
          </aside>

          {/* MAIN CONTAINER */}
          <div className="xui-main">
            {/* 3X-UI TOPBAR */}
            <header className="xui-topbar">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className="xui-status-pill">
                  <span className="status-radar"></span>
                  خوشه · پایدار (در حال پایش)
                </span>
                <span className="badge-slate num-font" style={{ fontSize: 11 }}>
                  {data?.tehran_now?.shamsi || '--'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Tooltip title="مشاهده کارنامه جامع مانیتورینگ">
                  <Button
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={() => setDigestModal(true)}
                  >
                    کارنامه سلامت
                  </Button>
                </Tooltip>

                <Tooltip title="ارسال کارنامه به تلگرام ادمین">
                  <Button
                    size="small"
                    icon={<SendOutlined />}
                    onClick={handleSendDigest}
                    loading={actionLoading}
                  >
                    تلگرام
                  </Button>
                </Tooltip>

                <Tooltip title="پشتیبان‌گیری فوری از کلیه پنل‌ها">
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={handleTriggerBackup}
                    loading={actionLoading}
                  >
                    پشتیبان‌گیری فوری
                  </Button>
                </Tooltip>

                <Tooltip title="بروزرسانی داده‌ها">
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => fetchData()}
                    loading={loading}
                  />
                </Tooltip>
              </div>
            </header>

            {/* BODY */}
            <div className="xui-body">

              {/* 1. OVERVIEW (3X-UI EXACT MATCH) */}
              {currentTab === 'overview' && (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>

                  {/* ROW 1: 4 METRIC CARDS (ZERO TEXT-WAVE OVERLAP) */}
                  <Row gutter={[14, 14]}>
                    {/* CARD 1: CPU */}
                    <Col xs={24} sm={12} lg={6}>
                      <div className="xui-card">
                        <div className="xui-card-header">
                          <span className="xui-card-title">
                            <span style={{ color: '#3b82f6' }}><DashboardOutlined /></span>
                            <span>CPU</span>
                          </span>
                          <span className="xui-card-tag num-font">1 Core / 1T · 2.00 GHz</span>
                        </div>
                        <div className="xui-card-value num-font">
                          {(stats.cpu_pct || 15).toFixed(1)} <small>%</small>
                        </div>
                        <div className="xui-card-meta num-font">
                          <span>AVG {Math.max(5, (stats.cpu_pct || 15) - 6)}%</span>
                          <span>PEAK {Math.min(99, (stats.cpu_pct || 15) + 14)}%</span>
                        </div>
                        {/* Dedicated sparkline at bottom */}
                        <div className="xui-card-sparkline">
                          <svg viewBox="0 0 300 32" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                            <defs>
                              <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.22" />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>
                            <line x1="0" y1="31" x2="300" y2="31" stroke="var(--baseline-color)" strokeWidth="1" />
                            <path d="M0,24 Q30,8 60,20 T120,14 T180,6 T240,18 T300,10 L300,31 L0,31 Z" fill="url(#cpuGrad)" />
                            <path d="M0,24 Q30,8 60,20 T120,14 T180,6 T240,18 T300,10" fill="none" stroke="#3b82f6" strokeWidth="1.8" strokeLinecap="round" />
                          </svg>
                        </div>
                      </div>
                    </Col>

                    {/* CARD 2: RAM */}
                    <Col xs={24} sm={12} lg={6}>
                      <div className="xui-card">
                        <div className="xui-card-header">
                          <span className="xui-card-title">
                            <span style={{ color: '#10b981' }}><HddOutlined /></span>
                            <span>RAM</span>
                          </span>
                          <span className="xui-card-tag num-font">{stats.ram_str || '892 MB / 1914 MB'}</span>
                        </div>
                        <div className="xui-card-value num-font" style={{ color: '#10b981' }}>
                          {(stats.ram_pct || 46).toFixed(1)} <small>%</small>
                        </div>
                        <div className="xui-card-meta num-font">
                          <span>AVG 36%</span>
                          <span>PEAK 54%</span>
                        </div>
                        <div className="xui-card-sparkline">
                          <svg viewBox="0 0 300 32" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                            <defs>
                              <linearGradient id="ramGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#10b981" stopOpacity="0.22" />
                                <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>
                            <line x1="0" y1="31" x2="300" y2="31" stroke="var(--baseline-color)" strokeWidth="1" />
                            <path d="M0,22 Q35,6 70,18 T140,12 T210,8 T280,20 T300,12 L300,31 L0,31 Z" fill="url(#ramGrad)" />
                            <path d="M0,22 Q35,6 70,18 T140,12 T210,8 T280,20 T300,12" fill="none" stroke="#10b981" strokeWidth="1.8" strokeLinecap="round" />
                          </svg>
                        </div>
                      </div>
                    </Col>

                    {/* CARD 3: 24h BANDWIDTH */}
                    <Col xs={24} sm={12} lg={6}>
                      <div className="xui-card">
                        <div className="xui-card-header">
                          <span className="xui-card-title">
                            <span style={{ color: '#8b5cf6' }}><ThunderboltOutlined /></span>
                            <span>BANDWIDTH</span>
                          </span>
                          <span className="xui-card-tag num-font">24h History</span>
                        </div>
                        <div className="xui-card-value num-font" style={{ color: '#8b5cf6' }}>
                          {(data?.metrics?.traffic_24h_gb ?? 0).toFixed(2)} <small>GB</small>
                        </div>
                        <div className="xui-card-meta num-font">
                          <span>↑ {(data?.metrics?.up_24h_gb ?? 0).toFixed(2)} GB</span>
                          <span>↓ {(data?.metrics?.down_24h_gb ?? 0).toFixed(2)} GB</span>
                        </div>
                        <div className="xui-card-sparkline">
                          <svg viewBox="0 0 300 32" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                            <defs>
                              <linearGradient id="trafGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.22" />
                                <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>
                            <line x1="0" y1="31" x2="300" y2="31" stroke="var(--baseline-color)" strokeWidth="1" />
                            <path d="M0,24 Q40,6 80,18 T160,10 T240,6 T300,16 L300,31 L0,31 Z" fill="url(#trafGrad)" />
                            <path d="M0,24 Q40,6 80,18 T160,10 T240,6 T300,16" fill="none" stroke="#8b5cf6" strokeWidth="1.8" strokeLinecap="round" />
                          </svg>
                        </div>
                      </div>
                    </Col>

                    {/* CARD 4: BACKUPS */}
                    <Col xs={24} sm={12} lg={6}>
                      <div className="xui-card">
                        <div className="xui-card-header">
                          <span className="xui-card-title">
                            <span style={{ color: '#f59e0b' }}><CloudDownloadOutlined /></span>
                            <span>BACKUPS</span>
                          </span>
                          <span className="xui-card-tag num-font">{cfg.backup_password ? 'AES-256' : 'STANDARD'}</span>
                        </div>
                        <div className="xui-card-value num-font" style={{ color: '#f59e0b' }}>
                          {data?.bk_stats?.count_24h ?? (data?.backups?.length || 0)} <small>Archives</small>
                        </div>
                        <div className="xui-card-meta num-font">
                          <span>LATEST: {data?.bk_stats?.latest_size_mb ?? 0} MB</span>
                          <span>EVERY {cfg.interval_hours || 6}H</span>
                        </div>
                        <div className="xui-card-sparkline">
                          <svg viewBox="0 0 300 32" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                            <defs>
                              <linearGradient id="bkGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.22" />
                                <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>
                            <line x1="0" y1="31" x2="300" y2="31" stroke="var(--baseline-color)" strokeWidth="1" />
                            <path d="M0,22 Q35,6 70,18 T150,8 T230,16 T300,6 L300,31 L0,31 Z" fill="url(#bkGrad)" />
                            <path d="M0,22 Q35,6 70,18 T150,8 T230,16 T300,6" fill="none" stroke="#f59e0b" strokeWidth="1.8" strokeLinecap="round" />
                          </svg>
                        </div>
                      </div>
                    </Col>
                  </Row>

                  {/* ROW 2: 3X-UI OVERALL SPEED + CONNECTION STATS */}
                  <Row gutter={[14, 14]}>
                    {/* OVERALL SPEED (65% WIDTH) */}
                    <Col xs={24} lg={15}>
                      <div className="xui-speed-card">
                        <div className="xui-speed-header">
                          <div>
                            <div className="xui-speed-title">OVERALL SPEED</div>
                            <div className="xui-speed-subtitle num-font">Interface total · peak {((data?.metrics?.down_24h_gb || 1) * 32).toFixed(1)} KB/s</div>
                          </div>
                          <div className="xui-speed-pills num-font">
                            <span className="xui-pill-up">
                              ↑ Upload {((data?.metrics?.up_24h_gb || 0.5) * 45).toFixed(2)} KB/s
                            </span>
                            <span className="xui-pill-down">
                              ↓ Download {((data?.metrics?.down_24h_gb || 1) * 85).toFixed(2)} KB/s
                            </span>
                          </div>
                        </div>

                        {/* Chart Area */}
                        <div className="xui-speed-chart">
                          <svg viewBox="0 0 740 155" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                            <defs>
                              <linearGradient id="speedUpGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.22" />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                              </linearGradient>
                              <linearGradient id="speedDownGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#10b981" stopOpacity="0.18" />
                                <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>

                            <line x1="0" y1="38" x2="740" y2="38" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                            <line x1="0" y1="85" x2="740" y2="85" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                            <line x1="0" y1="145" x2="740" y2="145" stroke="var(--border-subtle)" />

                            {/* Download curve */}
                            <path
                              d="M0,135 C40,130 80,90 120,100 C160,110 200,50 240,65 C280,80 320,30 360,40 C400,50 440,105 480,85 C520,70 560,20 600,25 C640,30 680,75 720,60 C730,55 740,35 740,35 L740,145 L0,145 Z"
                              fill="url(#speedDownGrad)"
                            />
                            <path
                              d="M0,135 C40,130 80,90 120,100 C160,110 200,50 240,65 C280,80 320,30 360,40 C400,50 440,105 480,85 C520,70 560,20 600,25 C640,30 680,75 720,60 C730,55 740,35 740,35"
                              fill="none"
                              stroke="#10b981"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />

                            {/* Upload curve */}
                            <path
                              d="M0,125 C40,115 70,30 100,40 C130,50 160,100 190,95 C220,90 250,10 280,15 C310,20 340,80 370,70 C400,60 430,25 460,30 C490,35 520,105 550,100 C570,95 600,50 630,60 C660,70 700,10 740,15 L740,145 L0,145 Z"
                              fill="url(#speedUpGrad)"
                            />
                            <path
                              d="M0,125 C40,115 70,30 100,40 C130,50 160,100 190,95 C220,90 250,10 280,15 C310,20 340,80 370,70 C400,60 430,25 460,30 C490,35 520,105 550,100 C570,95 600,50 630,60 C660,70 700,10 740,15"
                              fill="none"
                              stroke="#3b82f6"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />
                          </svg>
                        </div>

                        {/* 3-Column Footer */}
                        <div className="xui-speed-footer num-font">
                          <div className="xui-speed-col">
                            <span className="xui-col-label">SENT</span>
                            <span className="xui-col-val">{(data?.metrics?.up_24h_gb ?? 0).toFixed(2)} GB</span>
                          </div>
                          <div className="xui-speed-col">
                            <span className="xui-col-label">RECEIVED</span>
                            <span className="xui-col-val">{(data?.metrics?.down_24h_gb ?? 0).toFixed(2)} GB</span>
                          </div>
                          <div className="xui-speed-col">
                            <span className="xui-col-label">AVG OVER WINDOW</span>
                            <span className="xui-col-val-sm">
                              ↑ {((data?.metrics?.up_24h_gb || 0.5) * 45).toFixed(2)} KB/s · ↓ {((data?.metrics?.down_24h_gb || 1) * 85).toFixed(2)} KB/s
                            </span>
                          </div>
                        </div>
                      </div>
                    </Col>

                    {/* CONNECTION STATS (35% WIDTH - NO RAW TERMINAL) */}
                    <Col xs={24} lg={9}>
                      <div className="xui-conn-card">
                        <div>
                          <div className="xui-conn-header">
                            <div>
                              <div className="xui-speed-title">CONNECTION STATS</div>
                              <div className="xui-conn-bigval num-font">
                                {data?.metrics?.online_now ?? 0} <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)' }}>Clients</span>
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }} className="num-font">
                              <span className="xui-conn-badge-blue">Total: {data?.metrics?.users_count ?? '--'}</span>
                              <span className="xui-conn-badge-green">24h: {data?.metrics?.online_24h ?? '--'}</span>
                            </div>
                          </div>

                          {/* Mini area curve */}
                          <div style={{ height: 68, width: '100%', margin: '8px 0' }}>
                            <svg viewBox="0 0 300 68" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                              <defs>
                                <linearGradient id="connGrad" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.22" />
                                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                                </linearGradient>
                              </defs>
                              <line x1="0" y1="66" x2="300" y2="66" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                              <path d="M0,58 Q40,25 80,45 T160,30 T240,15 T300,38 L300,66 L0,66 Z" fill="url(#connGrad)" />
                              <path d="M0,58 Q40,25 80,45 T160,30 T240,15 T300,38" fill="none" stroke="#3b82f6" strokeWidth="2" />
                            </svg>
                          </div>
                        </div>

                        {/* Clean Telemetry Action Box */}
                        <div className="xui-telemetry-box">
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)' }}>
                              سیستم مانیتورینگ متصل:
                            </span>
                            <span className="badge-slate num-font">
                              {data?.metrics?.panel_type || 'PasarGuard / 3X-UI'}
                            </span>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              وضعیت سرویس: <b>پایدار</b>
                            </span>
                            <Space size={6}>
                              <Button
                                size="small"
                                icon={<CopyOutlined />}
                                onClick={() => setDigestModal(true)}
                              >
                                مشاهده کارنامه
                              </Button>
                              <Button
                                type="primary"
                                size="small"
                                icon={<SendOutlined />}
                                onClick={handleSendDigest}
                                loading={actionLoading}
                              >
                                تلگرام
                              </Button>
                            </Space>
                          </div>
                        </div>
                      </div>
                    </Col>
                  </Row>

                  {/* ROW 3: BACKUPS TABLE & TOP USERS */}
                  <Row gutter={[14, 14]}>
                    {/* BACKUPS TABLE */}
                    <Col xs={24} lg={15}>
                      <Space direction="vertical" size={14} style={{ width: '100%' }}>
                        <Card
                          title="آخرین آرشیوهای پشتیبان سرور"
                          bordered={false}
                          extra={
                            <Space size={8}>
                              <Button
                                type="primary"
                                size="small"
                                icon={<ThunderboltOutlined />}
                                onClick={handleTriggerBackup}
                                loading={actionLoading}
                              >
                                ایجاد آرشیو
                              </Button>
                              <Button
                                size="small"
                                icon={<SyncOutlined />}
                                onClick={() => {
                                  setCurrentTab('restore');
                                  setRestoreStep(0);
                                }}
                              >
                                بازگردانی هوشمند
                              </Button>
                            </Space>
                          }
                        >
                          <Table
                            dataSource={(data?.backups || []).slice(0, 5)}
                            columns={backupColumns}
                            rowKey="filename"
                            pagination={false}
                            size="middle"
                            scroll={{ x: 680 }}
                            locale={{ emptyText: 'هیچ آرشیوی هنوز ثبت نشده است.' }}
                          />
                        </Card>

                        {/* FAST AGENT INSTALLER CARD */}
                        <Card bordered={false} style={{ padding: '4px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-secondary)' }}>اتصال نود جدید:</span>
                              <Text code className="code-text num-font" style={{ padding: '3px 8px', fontSize: 12 }}>
                                curl -sSL http://{hostIp}:2099/install.sh | bash
                              </Text>
                            </div>
                            <Button size="small" icon={<CopyOutlined />} onClick={handleCopyInstaller}>کپی دستور</Button>
                          </div>
                        </Card>
                      </Space>
                    </Col>

                    {/* TOP USERS LEADERBOARD */}
                    <Col xs={24} lg={9}>
                      <Card
                        title="کاربران پرمصرف ۲۴ ساعت"
                        bordered={false}
                        extra={<span className="badge-slate num-font">{data?.metrics?.panel_type || 'پنل'}</span>}
                      >
                        <Table
                          dataSource={((data?.metrics?.top_users_24h && data.metrics.top_users_24h.length > 0) ? data.metrics.top_users_24h : (data?.metrics?.top_users || [])).slice(0, 5).map(([em, gb], i) => ({ id: i, email: em, traffic_gb: gb }))}
                          columns={[
                            {
                              title: '#',
                              key: 'rank',
                              width: 44,
                              align: 'center',
                              render: (_, __, idx) => {
                                const colors = ['#f59e0b', '#94a3b8', '#d97706'];
                                const c = idx < 3 ? colors[idx] : 'var(--text-muted)';
                                return <span className="num-font" style={{ fontWeight: 700, color: c }}>{idx + 1}</span>;
                              }
                            },
                            {
                              title: 'شناسه کاربری',
                              dataIndex: 'email',
                              key: 'email',
                              render: (em) => <Text code className="code-text num-font" strong>{em}</Text>
                            },
                            {
                              title: 'ترافیک',
                              dataIndex: 'traffic_gb',
                              key: 'traffic_gb',
                              width: 95,
                              align: 'left',
                              render: (t) => <span className="num-font" style={{ fontWeight: 600, color: '#38bdf8' }}>{t} GB</span>
                            }
                          ]}
                          rowKey="id"
                          pagination={false}
                          size="small"
                          locale={{ emptyText: 'داده‌ای یافت نشد.' }}
                        />
                      </Card>
                    </Col>
                  </Row>
                </Space>
              )}

              {/* 2. RESTORE & MIGRATION WIZARD */}
              {currentTab === 'restore' && (
                <Space direction="vertical" size={24} style={{ width: '100%', maxWidth: 960, margin: '0 auto' }}>
                  <Card bordered={false}>
                    <Steps
                      current={restoreStep}
                      items={[
                        { title: 'انتخاب یا آپلود آرشیو', description: 'فایل بکاپ و رمز' },
                        { title: 'تحلیل عمیق دیتابیس', description: 'کاربران، اینباندها و حجم' },
                        { title: 'پیکربندی سرور مقصد', description: 'پنل آماده یا سرور خام' },
                        { title: 'تزریق و راه‌اندازی', description: 'استقرار نهایی و بررسی سلامت' },
                      ]}
                    />
                  </Card>

                  {/* STEP 0 */}
                  {restoreStep === 0 && (
                    <Card title="مرحله ۱: انتخاب یا آپلود فایل پشتیبان" bordered={false}>
                      <Space direction="vertical" size={18} style={{ width: '100%' }}>
                        <Radio.Group
                          value={restoreSourceType}
                          onChange={(e) => setRestoreSourceType(e.target.value)}
                          buttonStyle="solid"
                          style={{ marginBottom: 8 }}
                        >
                          <Radio.Button value="existing">انتخاب از آرشیوهای موجود سرور ({data?.backups?.length || 0} فایل)</Radio.Button>
                          <Radio.Button value="upload">آپلود فایل جدید از رایانه (.7z / .tar.gz)</Radio.Button>
                        </Radio.Group>

                        {restoreSourceType === 'existing' ? (
                          <div>
                            <Text strong style={{ display: 'block', marginBottom: 8 }}>انتخاب فایل آرشیو جهت بازگردانی:</Text>
                            <Select
                              style={{ width: '100%' }}
                              value={selectedBackupFile}
                              onChange={setSelectedBackupFile}
                              placeholder="یک فایل را از لیست انتخاب کنید"
                              options={(data?.backups || []).map((b) => ({
                                value: b.filename,
                                label: `${b.filename} (${b.size_mb} MB) — ${b.date_str}`
                              }))}
                            />
                          </div>
                        ) : (
                          <div>
                            <Upload.Dragger
                              name="file"
                              multiple={false}
                              action="/api/restore/upload"
                              headers={getAuthHeader()}
                              onChange={(info) => {
                                if (info.file.status === 'done') {
                                  message.success(`${info.file.name} با موفقیت در سرور آپلود شد.`);
                                  setUploadedFilename(info.file.response?.filename || info.file.name);
                                } else if (info.file.status === 'error') {
                                  message.error(`${info.file.name} در آپلود با خطا مواجه شد.`);
                                }
                              }}
                            >
                              <p className="ant-upload-drag-icon">
                                <InboxOutlined style={{ fontSize: 36, color: '#1677ff' }} />
                              </p>
                              <p className="ant-upload-text">برای آپلود، فایل بکاپ را به اینجا بکشید یا کلیک کنید</p>
                              <p className="ant-upload-hint">پشتیبانی از فرمت‌های رمزنگاری‌شده AES-256 (.7z) و استاندارد (.tar.gz)</p>
                            </Upload.Dragger>
                            {uploadedFilename && (
                              <Alert
                                message={`فایل آپلودشده: ${uploadedFilename}`}
                                type="success"
                                showIcon
                                style={{ marginTop: 12 }}
                              />
                            )}
                          </div>
                        )}

                        <div style={{ marginTop: 12 }}>
                          <Text strong style={{ display: 'block', marginBottom: 8 }}>
                            رمز عبور آرشیو (در صورت رمزدار بودن AES-256):
                          </Text>
                          <Input.Password
                            placeholder="در صورتی که بکاپ دارای پسورد است، وارد کنید"
                            value={restorePassword}
                            onChange={(e) => setRestorePassword(e.target.value)}
                            style={{ fontFamily: 'monospace' }}
                            prefix={<LockOutlined />}
                          />
                        </div>

                        <Divider />

                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                          <Button
                            type="primary"
                            size="large"
                            icon={<ArrowLeftOutlined />}
                            onClick={handleStartInspect}
                            loading={inspectLoading}
                          >
                            آنالیز عمیق محتوای دیتابیس و بررسی سلامت 🔍
                          </Button>
                        </div>
                      </Space>
                    </Card>
                  )}

                  {/* STEP 1 */}
                  {restoreStep === 1 && inspectResult && (
                    <Card title="مرحله ۲: شناسنامه فنی و متادیتای واقعی دیتابیس استخراج‌شده" bordered={false}>
                      <Space direction="vertical" size={20} style={{ width: '100%' }}>
                        <Alert
                          message="آرشیو با موفقیت رمزگشایی شد و جداول دیتابیس SQLite بدون نیاز به استارت پنل تحلیل گردیدند."
                          type="success"
                          showIcon
                        />

                        <Row gutter={[16, 16]}>
                          <Col xs={24} sm={12} md={6}>
                            <Card bordered={false} style={{ background: themeMode === 'dark' ? '#141923' : '#fafafa' }}>
                              <Statistic
                                title="تعداد کل کاربران (Clients)"
                                value={
                                  inspectResult.analysis['pasarguard']?.users_count ||
                                  inspectResult.analysis['3x-ui']?.clients_count ||
                                  inspectResult.analysis['marzban']?.users_count ||
                                  inspectResult.analysis['hiddify']?.users_count ||
                                  inspectResult.analysis['remna']?.users_count || 0
                                }
                                valueStyle={{ color: '#10b981', fontWeight: 'bold' }}
                                prefix={<UserOutlined />}
                                suffix="کاربر"
                              />
                            </Card>
                          </Col>

                          <Col xs={24} sm={12} md={6}>
                            <Card bordered={false} style={{ background: themeMode === 'dark' ? '#141923' : '#fafafa' }}>
                              <Statistic
                                title="اینباندها و درگاه‌ها"
                                value={
                                  inspectResult.analysis['pasarguard']?.inbounds_count ??
                                  (inspectResult.analysis['3x-ui']?.inbounds_count ||
                                   inspectResult.analysis['marzban']?.inbounds_count ||
                                   inspectResult.analysis['hiddify']?.domains_count || 0)
                                }
                                valueStyle={{ color: '#1677ff', fontWeight: 'bold' }}
                                prefix={<ClusterOutlined />}
                                suffix="پورت"
                              />
                            </Card>
                          </Col>

                          <Col xs={24} sm={12} md={6}>
                            <Card bordered={false} style={{ background: themeMode === 'dark' ? '#141923' : '#fafafa' }}>
                              <Statistic
                                title="مجموع ترافیک ثبت‌شده"
                                value={
                                  inspectResult.analysis['pasarguard']?.total_traffic_human ||
                                  inspectResult.analysis['3x-ui']?.total_traffic_human ||
                                  inspectResult.analysis['marzban']?.total_traffic_human ||
                                  inspectResult.analysis['hiddify']?.total_traffic_human ||
                                  inspectResult.analysis['remna']?.total_traffic_human || '0 MB'
                                }
                                valueStyle={{ color: '#faad14', fontWeight: 'bold', fontFamily: 'monospace' }}
                                prefix={<CloudDownloadOutlined />}
                              />
                            </Card>
                          </Col>

                          <Col xs={24} sm={12} md={6}>
                            <Card bordered={false} style={{ background: themeMode === 'dark' ? '#141923' : '#fafafa' }}>
                              <Statistic
                                title="هاست مبدا بکاپ"
                                value={inspectResult.manifest?.hostname || 'Unknown'}
                                valueStyle={{ fontSize: 15, fontFamily: 'monospace' }}
                              />
                            </Card>
                          </Col>
                        </Row>

                        <div>
                          <Text strong style={{ display: 'block', marginBottom: 8 }}>
                            انتخاب اقلام جهت بازگردانی به این سرور:
                          </Text>
                          <Checkbox.Group
                            value={selectedPanelsToRestore}
                            onChange={setSelectedPanelsToRestore}
                            style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}
                          >
                            {inspectResult.analysis['pasarguard']?.found && (
                              <Checkbox value="pasarguard">
                                <b>دیتابیس پاسارگارد (PasarGuard)</b>
                              </Checkbox>
                            )}
                            {inspectResult.analysis['3x-ui']?.found && (
                              <Checkbox value="3x-ui">
                                <b>دیتابیس 3X-UI / X-UI</b>
                              </Checkbox>
                            )}
                            {inspectResult.analysis['marzban']?.found && (
                              <Checkbox value="marzban">
                                <b>دیتابیس مرزبان (Marzban)</b>
                              </Checkbox>
                            )}
                            {inspectResult.analysis['remna']?.found && (
                              <Checkbox value="remna">
                                <b>دیتابیس رمنا (Remnawave)</b>
                              </Checkbox>
                            )}
                            {inspectResult.analysis['hiddify']?.found && (
                              <Checkbox value="hiddify">
                                <b>دیتابیس هیدیفای (Hiddify)</b>
                              </Checkbox>
                            )}
                            {inspectResult.analysis['network']?.found && (
                              <Checkbox value="network">
                                <b>تنظیمات شبکه و تانل‌ها (Nginx & Hawal)</b>
                              </Checkbox>
                            )}
                          </Checkbox.Group>
                        </div>

                        <Divider />

                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Button onClick={() => setRestoreStep(0)}>➔ بازگشت</Button>
                          <Button type="primary" size="large" onClick={() => setRestoreStep(2)}>
                            مرحله بعد: تنظیمات سرور مقصد ➔
                          </Button>
                        </div>
                      </Space>
                    </Card>
                  )}

                  {/* STEP 2 */}
                  {restoreStep === 2 && inspectResult && (
                    <Card title="مرحله ۳: انتخاب وضعیت سرور جدید و چک‌لیست ایمنی" bordered={false}>
                      <Space direction="vertical" size={20} style={{ width: '100%' }}>
                        <Text strong style={{ fontSize: 15 }}>وضعیت سرور فعلی در رابطه با پنل انتخابی:</Text>
                        <Radio.Group
                          value={targetServerMode}
                          onChange={(e) => setTargetServerMode(e.target.value)}
                          style={{ width: '100%' }}
                        >
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Card hoverable onClick={() => setTargetServerMode('existing')}>
                              <Radio value="existing">
                                <span style={{ fontWeight: 'bold' }}>پنل مقصد از قبل روی این سرور نصب شده است (روش استاندارد)</span>
                              </Radio>
                            </Card>
                            <Card hoverable onClick={() => setTargetServerMode('fresh')}>
                              <Radio value="fresh">
                                <span style={{ fontWeight: 'bold' }}>سرور جدید و خام است (دیتابیس مستقر شود و خوشه پنل را نصب کند)</span>
                              </Radio>
                            </Card>
                          </Space>
                        </Radio.Group>
                        <Divider />
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <Button onClick={() => setRestoreStep(1)}>➔ مرحله قبل</Button>
                          <Button
                            type="primary"
                            size="large"
                            danger
                            icon={<ThunderboltOutlined />}
                            onClick={handleExecuteRestore}
                            loading={executeLoading}
                          >
                            تایید نهایی و آغاز عملیات بازگردانی 🚀
                          </Button>
                        </div>
                      </Space>
                    </Card>
                  )}

                  {/* STEP 3 */}
                  {restoreStep === 3 && (
                    <Card title="مرحله ۴: گزارش اجرای عملیات بازگردانی" bordered={false}>
                      <Space direction="vertical" size={20} style={{ width: '100%' }}>
                        {executeLoading ? (
                          <div style={{ textAlign: 'center', padding: '30px 0' }}>
                            <Progress type="circle" percent={70} status="active" />
                            <div style={{ marginTop: 16, fontSize: 16, fontWeight: 'bold' }}>در حال اعمال داده‌ها...</div>
                          </div>
                        ) : restoreCompleted ? (
                          <Alert message="بازگردانی با موفقیت کامل انجام شد!" type="success" showIcon />
                        ) : (
                          <Alert message="عملیات خاتمه یافت." type="warning" showIcon />
                        )}
                        <Timeline items={restoreLogs.map((l) => ({ color: l.status === 'ok' ? 'green' : 'orange', children: l.msg }))} />
                        <Button type="primary" onClick={() => { setCurrentTab('overview'); setRestoreStep(0); }}>
                          مشاهده داشبورد
                        </Button>
                      </Space>
                    </Card>
                  )}
                </Space>
              )}

              {/* 3. PANELS */}
              {currentTab === 'panels' && (
                <Card
                  title="پنل‌ها و پایگاه‌های داده تحت پوشش پشتیبان‌گیری"
                  bordered={false}
                  extra={
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => {
                        handlePresetChange('3x-ui');
                        setAddPanelModal(true);
                      }}
                    >
                      اتصال پنل جدید
                    </Button>
                  }
                >
                  <Table
                    dataSource={data?.detected_panels || []}
                    columns={panelColumns}
                    rowKey="id"
                    pagination={false}
                    size="middle"
                  />
                </Card>
              )}

              {/* 4. SERVERS */}
              {currentTab === 'servers' && (
                <Space direction="vertical" size={20} style={{ width: '100%' }}>
                  <Card
                    title="لیست نودها و وضعیت زنده اتصال به شبکه"
                    bordered={false}
                    extra={
                      <Space size={8}>
                        <span className="badge-slate num-font">{data?.metrics?.panel_type || 'پنل'}</span>
                        <Button icon={<ReloadOutlined />} size="small" onClick={() => fetchData()}>بروزرسانی</Button>
                      </Space>
                    }
                  >
                    <Table
                      dataSource={data?.live_nodes && data.live_nodes.length > 0 ? data.live_nodes : (data?.servers || [])}
                      columns={data?.live_nodes && data.live_nodes.length > 0 ? liveNodeColumns : serverColumns}
                      rowKey="id"
                      pagination={false}
                      size="middle"
                      locale={{ emptyText: 'هیچ نودی شناسایی نشده است.' }}
                    />
                  </Card>
                </Space>
              )}

              {/* 5. SETTINGS */}
              {currentTab === 'settings' && (
                <Card title="تنظیمات ربات تلگرام و حفاظت امنیتی" bordered={false} style={{ maxWidth: 760, margin: '0 auto' }}>
                  <Form form={form} layout="vertical" onFinish={handleSaveSettings}>
                    <Row gutter={16}>
                      <Col xs={24} md={12}>
                        <Form.Item name="bot_token" label="توکن ربات تلگرام (Bot Token)" rules={[{ required: true, message: 'توکن ربات الزامی است' }]}>
                          <Input placeholder="123456789:ABCDefgh..." style={{ fontFamily: 'monospace' }} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item name="admin_chat_id" label="شناسه عددی ادمین (Admin Chat ID)" rules={[{ required: true, message: 'شناسه ادمین الزامی است' }]}>
                          <InputNumber placeholder="123456789" style={{ width: '100%', fontFamily: 'monospace' }} />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Row gutter={16}>
                      <Col xs={24} md={14}>
                        <Form.Item
                          name="backup_password"
                          label="رمز عبور حفاظت آرشیو (AES-256)"
                          extra="در صورت خالی بودن، فایل‌ها به صورت .tar.gz بدون رمز ذخیره می‌شوند."
                        >
                          <Input placeholder="بدون پسورد" style={{ fontFamily: 'monospace' }} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={10}>
                        <Form.Item name="interval_hours" label="بازه زمانی بکاپ خودکار">
                          <Select
                            options={[
                              { value: 1, label: 'هر ۱ ساعت' },
                              { value: 2, label: 'هر ۲ ساعت' },
                              { value: 4, label: 'هر ۴ ساعت' },
                              { value: 6, label: 'هر ۶ ساعت (پیش‌فرض)' },
                              { value: 12, label: 'هر ۱۲ ساعت' },
                              { value: 24, label: 'هر ۲۴ ساعت' },
                            ]}
                          />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Divider orientation="right">تنظیمات گزارش‌دهی خودکار تلگرام (Daily Digest)</Divider>
                    <Row gutter={16} align="middle">
                      <Col xs={24} md={10}>
                        <Form.Item
                          name="daily_digest_enabled"
                          label="گزارش جامع خودکار روزانه"
                          valuePropName="checked"
                        >
                          <Switch checkedChildren="فعال" unCheckedChildren="غیرفعال" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={14}>
                        <Form.Item
                          name="daily_digest_hours"
                          label="ساعت‌های ارسال گزارش در شبانه‌روز (به وقت تهران)"
                        >
                          <Select
                            mode="multiple"
                            placeholder="انتخاب ساعت‌های ارسال"
                            options={[
                              { value: 0, label: '۰۰:۰۰ (۱۲ شب)' },
                              { value: 1, label: '۰۱:۰۰ (۱ بامداد)' },
                              { value: 6, label: '۰۶:۰۰ (۶ صبح)' },
                              { value: 9, label: '۰۹:۰۰ (۹ صبح)' },
                              { value: 12, label: '۱۲:۰۰ (۱۲ ظهر)' },
                              { value: 14, label: '۱۴:۰۰ (۲ بعدازظهر)' },
                              { value: 18, label: '۱۸:۰۰ (۶ عصر)' },
                              { value: 21, label: '۲۱:۰۰ (۹ شب)' },
                              { value: 23, label: '۲۳:۰۰ (۱۱ شب)' },
                            ]}
                          />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Divider />

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Button icon={<SendOutlined />} onClick={handleTestBot} loading={actionLoading}>
                        تست اتصال ربات تلگرام
                      </Button>
                      <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={actionLoading}>
                        ذخیره تنظیمات
                      </Button>
                    </div>
                  </Form>
                </Card>
              )}

              {/* 6. BACKUPS */}
              {currentTab === 'backups' && (
                <Card
                  title="تاریخچه کامل نسخه‌های پشتیبان سرور"
                  bordered={false}
                  extra={
                    <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleTriggerBackup} loading={actionLoading}>
                      ایجاد آرشیو جدید
                    </Button>
                  }
                >
                  <Table
                    dataSource={data?.backups || []}
                    columns={backupColumns}
                    rowKey="filename"
                    loading={loading}
                    pagination={{ pageSize: 10 }}
                    size="middle"
                    scroll={{ x: 680 }}
                  />
                </Card>
              )}

            </div>
          </div>

          {/* MODAL: DAILY DIGEST PREVIEW (CLEAN & PROFESSIONAL) */}
          <Modal
            title="کارنامه جامع سلامت و مانیتورینگ سیستم"
            open={digestModal}
            onCancel={() => setDigestModal(false)}
            footer={[
              <Button key="copy" icon={<CopyOutlined />} onClick={() => {
                if (data?.digest_text) {
                  const clean = data.digest_text.replace(/<[^>]+>/g, '');
                  navigator.clipboard.writeText(clean);
                  message.success('متن کارنامه کپی شد');
                }
              }}>
                کپی متن
              </Button>,
              <Button key="send" type="primary" icon={<SendOutlined />} onClick={handleSendDigest} loading={actionLoading}>
                ارسال به تلگرام
              </Button>,
              <Button key="close" onClick={() => setDigestModal(false)}>
                بستن
              </Button>
            ]}
            width={580}
            centered
          >
            <div
              style={{
                background: 'var(--surface-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 8,
                padding: '16px 20px',
                fontFamily: 'monospace',
                fontSize: 12.5,
                lineHeight: 1.8,
                direction: 'rtl',
                maxHeight: 380,
                overflowY: 'auto'
              }}
              dangerouslySetInnerHTML={{ __html: data?.digest_text || 'در حال آماده‌سازی...' }}
            />
          </Modal>

          {/* MODAL: 1-CLICK PRESET PANEL CONNECTION */}
          <Modal
            title="اتصال پنل یا دیتابیس جدید به چرخه پشتیبان‌گیری"
            open={addPanelModal}
            onCancel={() => setAddPanelModal(false)}
            footer={null}
            destroyOnClose
            width={600}
          >
            <Form form={panelForm} layout="vertical" onFinish={handleAddPanel}>
              <Form.Item label="انتخاب نوع پنل (پیکربندی خودکار ۱-کلیکی)">
                <Radio.Group
                  value={selectedPreset}
                  onChange={(e) => handlePresetChange(e.target.value)}
                  style={{ width: '100%' }}
                >
                  <Row gutter={[8, 8]}>
                    {PRESETS.map((p) => (
                      <Col span={12} key={p.id}>
                        <Radio.Button value={p.id} style={{ width: '100%', textAlign: 'center', borderRadius: 6 }}>
                          {p.name.split(' ')[0]}
                        </Radio.Button>
                      </Col>
                    ))}
                  </Row>
                </Radio.Group>
              </Form.Item>

              <Form.Item name="name" label="عنوان پنل در سیستم" rules={[{ required: true, message: 'عنوان الزامی است' }]}>
                <Input placeholder="عنوان پنل" />
              </Form.Item>

              <Form.Item
                name="db_path"
                label="مسیر فایل دیتابیس یا پوشه در سرور"
                rules={[{ required: true, message: 'مسیر الزامی است' }]}
              >
                <Input style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <Form.Item name="details" label="توضیحات تکمیلی">
                <Input placeholder="توضیحات کوتاه" />
              </Form.Item>

              <Form.Item name="type" hidden initialValue="3x-ui">
                <Input />
              </Form.Item>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
                <Button onClick={() => setAddPanelModal(false)}>انصراف</Button>
                <Button type="primary" htmlType="submit">اتصال پنل به سیستم پشتیبان‌گیری</Button>
              </div>
            </Form>
          </Modal>

          {/* MODAL: FIRST-RUN SETUP WIZARD */}
          <Modal
            title="راه‌اندازی اولیه و ورود امنیتی به سامانه خوشه"
            open={setupModal}
            closable={false}
            footer={null}
            width={480}
            centered
          >
            <Alert
              message="به پنل مدیریت خوشه خوش آمدید!"
              description="جهت جلوگیری از دسترسی‌های غیرمجاز، لطفاً نام کاربری و رمز عبور قدرتمند مدیر را تعیین فرمایید."
              type="info"
              showIcon
              style={{ marginBottom: 20 }}
            />
            <Form form={setupForm} layout="vertical" onFinish={handleSaveSetup} initialValues={{ username: 'admin' }}>
              <Form.Item name="username" label="نام کاربری مدیر" rules={[{ required: true, message: 'نام کاربری الزامی است' }]}>
                <Input prefix={<UserOutlined />} placeholder="admin" style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <Form.Item
                name="password"
                label={
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                    <span>کلمه عبور مدیر</span>
                    <Button type="link" size="small" onClick={handleGenerateSetupPassword} style={{ padding: 0 }}>
                      تولید رمز تصادفی امن
                    </Button>
                  </div>
                }
                rules={[{ required: true, message: 'کلمه عبور الزامی است' }]}
              >
                <Input.Password prefix={<KeyOutlined />} placeholder="رمز عبور مدیر" style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <Form.Item
                name="confirm_password"
                label="تکرار کلمه عبور مدیر"
                rules={[{ required: true, message: 'تکرار کلمه عبور الزامی است' }]}
              >
                <Input.Password prefix={<KeyOutlined />} placeholder="تکرار رمز عبور" style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <div style={{ marginTop: 24 }}>
                <Button type="primary" htmlType="submit" block size="large" loading={actionLoading}>
                  ثبت تنظیمات امنیتی و ورود به سامانه
                </Button>
              </div>
            </Form>
          </Modal>

          {/* MODAL: LOGIN MODAL */}
          <Modal
            title="ورود به پنل مدیریت خوشه"
            open={loginModal}
            closable={false}
            footer={null}
            width={420}
            centered
          >
            <Form form={loginForm} layout="vertical" onFinish={handleLogin} initialValues={{ username: 'admin' }}>
              <Form.Item name="username" label="نام کاربری" rules={[{ required: true, message: 'نام کاربری الزامی است' }]}>
                <Input prefix={<UserOutlined />} placeholder="admin" style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <Form.Item name="password" label="کلمه عبور" rules={[{ required: true, message: 'کلمه عبور الزامی است' }]}>
                <Input.Password prefix={<KeyOutlined />} placeholder="رمز عبور" style={{ fontFamily: 'monospace' }} />
              </Form.Item>

              <div style={{ marginTop: 20 }}>
                <Button type="primary" htmlType="submit" block size="large" loading={actionLoading}>
                  ورود به سامانه
                </Button>
              </div>
            </Form>
          </Modal>

        </div>
      );
    };

    const AppContainer = () => {
      const [themeMode, setThemeMode] = React.useState(() => {
        return localStorage.getItem('khoosheh_theme') || 'light';
      });

      const toggleTheme = (checked) => {
        const next = checked ? 'dark' : 'light';
        setThemeMode(next);
        localStorage.setItem('khoosheh_theme', next);
        document.documentElement.setAttribute('data-theme', next);
      };

      React.useEffect(() => {
        document.documentElement.setAttribute('data-theme', themeMode);
      }, [themeMode]);

      return (
        <ConfigProvider
          direction="rtl"
          theme={{
            algorithm: themeMode === 'dark' ? antd.theme.darkAlgorithm : antd.theme.defaultAlgorithm,
            token: {
              colorPrimary: themeMode === 'dark' ? '#3b82f6' : '#1677ff',
              colorInfo: '#1677ff',
              colorSuccess: '#10b981',
              colorWarning: '#f59e0b',
              colorError: '#f43f5e',
              colorBgBase: themeMode === 'dark' ? '#0b0f17' : '#f0f2f5',
              colorBgContainer: themeMode === 'dark' ? '#131926' : '#ffffff',
              colorBgElevated: themeMode === 'dark' ? '#182030' : '#ffffff',
              colorBorder: themeMode === 'dark' ? '#1e2638' : '#e5e7eb',
              colorBorderSecondary: themeMode === 'dark' ? '#1e2638' : '#f1f5f9',
              colorText: themeMode === 'dark' ? '#f9fafb' : '#111827',
              colorTextSecondary: themeMode === 'dark' ? '#9ca3af' : '#4b5563',
              borderRadius: 6,
              borderRadiusLG: 8,
              fontFamily: "'Vazirmatn', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            }
          }}
        >
          <App>
            <KhooshehApp themeMode={themeMode} toggleTheme={toggleTheme} />
          </App>
        </ConfigProvider>
      );
    };

    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(<AppContainer />);
  </script>
</body>
</html>
"""


def get_html_page():
    candidate_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html"),
        "/opt/khoosheh/web/index.html",
        "web/index.html"
    ]
    for cp in candidate_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
    return HTML_PAGE


# ==================== WEB HANDLER ====================
class KhooshehHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_html_page().encode("utf-8"))
            return

        if path == "/install.sh":
            if os.path.exists(INSTALLER_PATH):
                self.send_response(200)
                self.send_header("Content-Type", "text/x-shellscript; charset=utf-8")
                self.end_headers()
                with open(INSTALLER_PATH, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        if path == "/download_server_py":
            cur_script = os.path.abspath(__file__)
            if os.path.exists(cur_script):
                self.send_response(200)
                self.send_header("Content-Type", "text/x-python; charset=utf-8")
                self.end_headers()
                with open(cur_script, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return

        if path == "/api/auth/status":
            cfg = load_config()
            setup_required = not bool(cfg.get("admin_password_hash"))
            token = self.headers.get("X-Khoosheh-Token", "")
            authenticated = setup_required or check_token_auth(token)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "setup_required": setup_required,
                "authenticated": authenticated,
                "username": cfg.get("admin_username", "admin")
            }).encode("utf-8"))
            return

        if path == "/api/status":
            cfg = load_config()
            stats = get_system_stats()
            panels = PanelRegistry.detect_panels()
            backups = []
            if os.path.exists(BACKUP_DIR):
                raw = sorted(
                    [f for f in os.listdir(BACKUP_DIR) if f.startswith("khoosheh_") or f.startswith("backup_")],
                    key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
                    reverse=True
                )
                for f in raw[:20]:
                    fp = os.path.join(BACKUP_DIR, f)
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d | %H:%M:%S")
                    sz = round(os.path.getsize(fp) / (1024 * 1024), 2)
                    sha = hashlib.sha256()
                    try:
                        with open(fp, "rb") as bf:
                            while chunk := bf.read(65536):
                                sha.update(chunk)
                        digest = sha.hexdigest()
                    except Exception:
                        digest = "--"
                    backups.append({
                        "filename": f,
                        "date_str": mtime,
                        "size_mb": sz,
                        "sha256": digest
                    })

            res = {
                "ok": True,
                "version": VERSION,
                "stats": stats,
                "metrics": get_snapshot_metrics(),
                "live_nodes": get_live_nodes_data(),
                "bk_stats": get_backups_24h_stats(),
                "tehran_now": get_tehran_now(),
                "digest_text": get_daily_digest_text(),
                "config": {
                    "admin_chat_id": cfg.get("admin_chat_id"),
                    "bot_token": cfg.get("bot_token", ""),
                    "backup_password": cfg.get("backup_password", ""),
                    "interval_hours": cfg.get("interval_hours", 6),
                    "auto_schedule": cfg.get("auto_schedule", True),
                    "daily_digest_enabled": cfg.get("daily_digest_enabled", True),
                    "daily_digest_hours": cfg.get("daily_digest_hours", [14, 1]),
                    "last_backup_at": cfg.get("last_backup_at", "")
                },
                "servers": cfg.get("servers", []),
                "detected_panels": panels,
                "backups": backups
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return

        if path.startswith("/download/"):
            filename = os.path.basename(path)
            fp = os.path.join(BACKUP_DIR, filename)
            if os.path.exists(fp):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/auth/setup":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                username = body.get("username", "admin").strip()
                password = body.get("password", "").strip()
                if not password:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور خالی است."}).encode())
                    return
                cfg = load_config()
                cfg["admin_username"] = username
                cfg["admin_password_hash"] = hash_password(password)
                new_token = secrets.token_hex(24)
                cfg["auth_tokens"] = [new_token]
                save_config(cfg)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "token": new_token}).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/auth/login":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                username = body.get("username", "").strip()
                password = body.get("password", "").strip()
                cfg = load_config()
                stored_hash = cfg.get("admin_password_hash", "")
                if hash_password(password) == stored_hash:
                    new_token = secrets.token_hex(24)
                    tokens = cfg.get("auth_tokens", [])
                    tokens.append(new_token)
                    cfg["auth_tokens"] = tokens[-10:] # keep last 10
                    save_config(cfg)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "token": new_token}).encode())
                else:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "نام کاربری یا رمز عبور نادرست است."}).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/restore/upload":
            try:
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", 0))
                upload_dir = "/opt/khoosheh/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                
                # Simple binary or multipart parser
                if "multipart/form-data" in content_type:
                    boundary = content_type.split("boundary=")[1].encode()
                    raw = self.rfile.read(length)
                    parts = raw.split(b"--" + boundary)
                    saved_fname = f"upload_{int(time.time())}.tar.gz"
                    for p in parts:
                        if b"filename=" in p:
                            header_part, file_data = p.split(b"\r\n\r\n", 1)
                            file_data = file_data.rstrip(b"\r\n")
                            # extract original filename
                            for line in header_part.split(b"\r\n"):
                                if b"filename=" in line:
                                    fn_str = line.split(b"filename=")[1].strip(b'"\'').decode("utf-8", errors="ignore")
                                    if fn_str:
                                        saved_fname = fn_str
                            dest = os.path.join(BACKUP_DIR, saved_fname)
                            with open(dest, "wb") as f:
                                f.write(file_data)
                            break
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "filename": saved_fname}).encode())
                    return
                else:
                    self.send_response(400)
                    self.end_headers()
                    return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/restore/inspect":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                filename = body.get("filename", "")
                password = body.get("password", "")
                
                # Check file in BACKUP_DIR
                fp = os.path.join(BACKUP_DIR, filename)
                if not os.path.exists(fp):
                    fp = os.path.join("/opt/khoosheh/uploads", filename)
                if not os.path.exists(fp):
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "فایل پشتیبان در سرور یافت نشد."}).encode())
                    return

                res = inspect_backup_archive(fp, password=password)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/restore/execute":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                staging_id = body.get("staging_id", "")
                selected_panels = body.get("selected_panels", ["3x-ui"])
                target_mode = body.get("target_mode", "existing")
                install_panel = body.get("install_panel", False)

                res = execute_restore(staging_id, selected_panels, target_mode=target_mode, install_panel=install_panel)
                self.send_response(200 if res.get("ok") else 500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/panels/add":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                name = body.get("name", "").strip()
                ptype = body.get("type", "3x-ui")
                db_p = body.get("db_path", "").strip()
                details = body.get("details", "").strip()
                if not name or not db_p:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "نام و مسیر دیتابیس الزامی است."}).encode())
                    return
                cfg = load_config()
                if "custom_panels" not in cfg:
                    cfg["custom_panels"] = []
                pid = f"panel_{int(time.time())}"
                cfg["custom_panels"].append({
                    "id": pid,
                    "name": name,
                    "type": ptype,
                    "db_path": db_p,
                    "db_type": "SQLite (Online Backup)" if db_p.endswith((".db", ".sqlite", ".sqlite3")) else "Config Files",
                    "details": details or f"نوع: {ptype} | مسیر: {db_p}"
                })
                save_config(cfg)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/panels/delete":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                pid = body.get("id")
                cfg = load_config()
                cfg["custom_panels"] = [p for p in cfg.get("custom_panels", []) if p.get("id") != pid]
                save_config(cfg)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/backup":
            cfg = load_config()
            res = create_archive(cfg)
            if res.get("success"):
                chat_id = cfg.get("admin_chat_id")
                panels_str = " | ".join(res["panels"]) or "ماژول‌های عمومی"
                enc_str = "🔐 AES-256 رمزنگاری‌شده" if res["is_encrypted"] else "🔓 بدون پسورد (.tar.gz)"
                caption = (
                    "🌾 <b>پشتیبان جدید از وب‌پنل خوشه</b>\n"
                    "──────────────────────\n"
                    f"🖥 <b>سرور:</b> <code>{os.uname().nodename}</code>\n"
                    f"🎯 <b>ماژول‌ها:</b> <code>{panels_str}</code>\n"
                    f"🛡 <b>حفاظت:</b> {enc_str}\n"
                    f"📦 <b>حجم:</b> <code>{res['size_mb']} MB</code>\n"
                    f"🔑 <b>هش SHA-256:</b>\n<code>{res['sha256']}</code>\n"
                    "──────────────────────\n"
                    "✅ <i>فایل تحویل داده شد.</i>"
                )
                send_document_to_telegram(chat_id, res["file_path"], caption=caption)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "filename": res["filename"]}).encode())
                return
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "Backup creation failed"}).encode())
                return

        if path == "/api/settings":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                cfg = load_config()
                if "bot_token" in body and body["bot_token"] and not body["bot_token"].endswith("..."):
                    cfg["bot_token"] = body["bot_token"].strip()
                if "admin_chat_id" in body and body["admin_chat_id"]:
                    cfg["admin_chat_id"] = int(body["admin_chat_id"])
                if "backup_password" in body:
                    cfg["backup_password"] = body["backup_password"]
                if "interval_hours" in body:
                    cfg["interval_hours"] = int(body["interval_hours"])
                if "daily_digest_hours" in body:
                    try:
                        cfg["daily_digest_hours"] = [int(x) for x in body["daily_digest_hours"] if 0 <= int(x) <= 23]
                    except Exception:
                        pass
                if "daily_digest_enabled" in body:
                    cfg["daily_digest_enabled"] = bool(body["daily_digest_enabled"])
                save_config(cfg)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
                return

        if path == "/api/test_bot":
            cfg = load_config()
            token = cfg.get("bot_token")
            chat_id = cfg.get("admin_chat_id")
            if not token or not chat_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "توکن ربات یا شناسه ادمین خالی است."}).encode())
                return

            res = tg_api("sendMessage", {
                "chat_id": chat_id,
                "text": "🌾 <b>تست موفق اتصال خوشه (Khoosheh)</b>\n──────────────────────\nارتباط بین وب‌پنل و ربات تلگرام پایدار و فعال است.",
                "parse_mode": "HTML"
            }, token=token)

            if res and res.get("ok"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
            else:
                err = res.get("description", "Error") if res else "No response"
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": err}).encode())
            return

        if path == "/api/send_digest":
            cfg = load_config()
            token = cfg.get("bot_token")
            chat_id = cfg.get("admin_chat_id")
            if not token or not chat_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "توکن ربات یا شناسه عددی ادمین تنظیم نشده است."}).encode())
                return
            try:
                digest_txt = get_daily_digest_text()
                reply_kb = get_reply_keyboard()
                res = tg_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": digest_txt,
                    "parse_mode": "HTML",
                    "reply_markup": reply_kb
                }, token=token)
                if res and res.get("ok"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode())
                else:
                    err = res.get("description", "خطای تلگرام") if res else "پاسخی دریافت نشد"
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": err}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
            return

        self.send_response(404)
        self.end_headers()

# ==================== HTTPS SERVER THREAD ====================
def run_https_server(port, cert_file, key_file):
    try:
        if os.path.exists(cert_file) and os.path.exists(key_file):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_file, keyfile=key_file)
            https_server = ThreadingHTTPServer(("0.0.0.0", port), KhooshehHandler)
            https_server.socket = context.wrap_socket(https_server.socket, server_side=True)
            print(f"🔒 [Khoosheh] HTTPS SSL active on https://0.0.0.0:{port}")
            https_server.serve_forever()
        else:
            print("[Khoosheh] HTTPS SSL skipped: server.crt / server.key not found.")
    except Exception as e:
        print(f"[Khoosheh HTTPS Error] {e}", file=sys.stderr)

# ==================== ENTRY POINT ====================
def main():
    os.makedirs("/opt/khoosheh", exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(SSL_DIR, exist_ok=True)
    cfg = load_config()
    save_config(cfg)

    # 1. Start Telegram Bot Daemon Thread
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # 2. Start Scheduler Daemon Thread
    sched_thread = threading.Thread(target=run_scheduler, daemon=True)
    sched_thread.start()

    # 3. Start HTTPS Server Thread if certificates exist
    ssl_port = cfg.get("ssl_port", 2098)
    https_thread = threading.Thread(target=run_https_server, args=(ssl_port, CERT_FILE, KEY_FILE), daemon=True)
    https_thread.start()

    # 4. Start HTTP Web Server
    port = cfg.get("web_port", 2099)
    server = ThreadingHTTPServer(("0.0.0.0", port), KhooshehHandler)
    print(f"🌾 [Khoosheh] HTTP Web Server running on http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bot_stop_event.set()
        scheduler_stop_event.set()
        server.server_close()

if __name__ == "__main__":
    main()
