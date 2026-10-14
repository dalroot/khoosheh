"""
Modular Panel Registry for Khoosheh
Discovers and collects data for 3X-UI, Marzban, PasarGuard, Remnawave, Hiddify, and Network configs.
"""
import os
import sqlite3
import shutil
import subprocess
import json

class PanelRegistry:
    @staticmethod
    def detect_panels(load_config_fn=None):
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

        if load_config_fn:
            cfg = load_config_fn()
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
    def collect(staging_dir, backup_type="full", load_config_fn=None):
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

        return collected
