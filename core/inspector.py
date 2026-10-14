"""
Deep Database Inspector & Archive Analysis for Khoosheh
Extracts users, inbounds, traffic and configurations directly from SQLite/archives.
"""
import os
import sqlite3
import subprocess
import json
import time
import secrets
import shutil
import tarfile

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

        # Read manifest.json
        manifest = {}
        manifest_file = os.path.join(staging_dir, "manifest.json")
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                pass

        # Inspect 3X-UI
        xui_report = {"found": False}
        xui_db_path = os.path.join(staging_dir, "3x-ui", "x-ui.db")
        if os.path.exists(xui_db_path):
            xui_report = deep_inspect_sqlite_3x_ui(xui_db_path)
            xui_report["has_certs"] = os.path.exists(os.path.join(staging_dir, "3x-ui", "certs"))

        # Inspect Marzban
        marzban_report = {"found": False}
        marzban_db_path = os.path.join(staging_dir, "marzban", "db.sqlite3")
        if os.path.exists(marzban_db_path):
            marzban_report = deep_inspect_sqlite_marzban(marzban_db_path)
            marzban_report["has_env"] = os.path.exists(os.path.join(staging_dir, "marzban", ".env"))
            marzban_report["has_compose"] = os.path.exists(os.path.join(staging_dir, "marzban", "docker-compose.yml"))
            marzban_report["has_sql"] = os.path.exists(os.path.join(staging_dir, "marzban", "marzban_dump.sql"))

        # Inspect PasarGuard
        pasarguard_report = {"found": False}
        pg_db_path = os.path.join(staging_dir, "pasarguard", "db.sqlite3")
        if os.path.exists(pg_db_path):
            pasarguard_report = deep_inspect_sqlite_pasarguard(pg_db_path)
            pasarguard_report["has_env"] = os.path.exists(os.path.join(staging_dir, "pasarguard", ".env"))
            pasarguard_report["has_compose"] = os.path.exists(os.path.join(staging_dir, "pasarguard", "docker-compose.yml"))
            pasarguard_report["has_certs"] = os.path.exists(os.path.join(staging_dir, "pasarguard", "certs"))

        # Inspect Remnawave
        remna_report = {"found": False}
        remna_dir = os.path.join(staging_dir, "remna")
        if os.path.exists(remna_dir):
            remna_report = deep_inspect_remnawave(remna_dir)

        # Inspect Hiddify
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

        # Inspect Network
        network_report = {
            "found": os.path.exists(os.path.join(staging_dir, "network")),
            "has_nginx": os.path.exists(os.path.join(staging_dir, "network", "nginx")),
            "has_hawal": os.path.exists(os.path.join(staging_dir, "network", "hawal")) or os.path.exists(os.path.join(staging_dir, "network", "etc_hawal")),
            "has_haproxy": os.path.exists(os.path.join(staging_dir, "network", "haproxy"))
        }

        # Target Server state
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
