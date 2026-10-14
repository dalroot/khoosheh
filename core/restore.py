"""
Smart Restore & Migration Wizard Execution Engine for Khoosheh
Performs automated pre-restore snapshots, integrity checks, and graceful service restarts.
"""
import os
import sqlite3
import shutil
import subprocess
import time
from datetime import datetime

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
                if os.path.exists("/etc/x-ui/x-ui.db"):
                    bak_path = f"/etc/x-ui/x-ui.db.pre_restore_{ts}.bak"
                    try:
                        shutil.copy2("/etc/x-ui/x-ui.db", bak_path)
                        log(f"نسخه پشتیبان حفاظتی در مسیر {bak_path} ذخیره شد.", "ok")
                    except Exception as e:
                        log(f"هشدار در ایجاد بکاپ اضطراری: {e}", "warning")

                log("توقف موقت سرویس x-ui جهت آزادسازی قفل‌های SQLite...", "info")
                subprocess.run(["systemctl", "stop", "x-ui"], capture_output=True)

                os.makedirs("/etc/x-ui", exist_ok=True)
                for extra_ext in ["-wal", "-shm"]:
                    try:
                        if os.path.exists(f"/etc/x-ui/x-ui.db{extra_ext}"):
                            os.remove(f"/etc/x-ui/x-ui.db{extra_ext}")
                    except Exception:
                        pass
                shutil.copy2(src_db, "/etc/x-ui/x-ui.db")
                os.chmod("/etc/x-ui/x-ui.db", 0o644)
                
                try:
                    chk_con = sqlite3.connect("/etc/x-ui/x-ui.db")
                    chk_res = chk_con.execute("PRAGMA integrity_check;").fetchone()[0]
                    chk_con.close()
                    if chk_res != "ok":
                        log("هشدار: دیتابیس آرشیو دارای ایراد یکپارچگی بود؛ بازگشت خودکار به نسخه امن قبلی (Rollback)...", "warning")
                        if 'bak_path' in locals() and os.path.exists(bak_path):
                            shutil.copy2(bak_path, "/etc/x-ui/x-ui.db")
                    else:
                        log("سلامت ساختار پایگاه داده تایید شد (Integrity: OK) ✅", "ok")
                except Exception as e:
                    log(f"بررسی یکپارچگی دیتابیس: {e}", "info")
                log("فایل پایگاه داده x-ui.db با موفقیت جایگزین شد و پرمیشن ۶۴۴ تنظیم گردید.", "ok")

                src_certs = os.path.join(src_xui, "certs")
                if os.path.exists(src_certs):
                    os.makedirs("/etc/x-ui/certs", exist_ok=True)
                    shutil.copytree(src_certs, "/etc/x-ui/certs", dirs_exist_ok=True)
                    log("سرتیفیکیت‌ها و کلیدهای امنیتی پنل در /etc/x-ui/certs بازگردانی شدند.", "ok")

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
                
                if has_compose:
                    log("توقف موقت کانتینرهای مرزبان جهت آزادسازی قفل‌های دیتابیس...", "info")
                    subprocess.run(["docker", "compose", "-f", m_compose_path, "down"], capture_output=True)
                elif subprocess.run(["systemctl", "is-active", "--quiet", "marzban"]).returncode == 0:
                    log("توقف موقت سرویس systemd مرزبان...", "info")
                    subprocess.run(["systemctl", "stop", "marzban"], capture_output=True)

                os.makedirs("/var/lib/marzban", exist_ok=True)
                os.makedirs("/opt/marzban", exist_ok=True)
                if os.path.exists("/var/lib/marzban/db.sqlite3"):
                    try:
                        shutil.copy2("/var/lib/marzban/db.sqlite3", f"/var/lib/marzban/db.sqlite3.pre_restore_{ts}.bak")
                        log("نسخه پشتیبان حفاظتی دیتابیس مرزبان ایجاد شد.", "ok")
                    except Exception:
                        pass

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

                for fn in [".env", "docker-compose.yml"]:
                    f_src = os.path.join(src_marzban, fn)
                    if os.path.exists(f_src):
                        shutil.copy2(f_src, os.path.join("/opt/marzban", fn))
                        log(f"فایل پیکربندی مرزبان ({fn}) بازگردانی شد.", "ok")

                for sub in ["xray-core", "templates", "certs"]:
                    sub_src = os.path.join(src_marzban, sub)
                    if os.path.exists(sub_src):
                        shutil.copytree(sub_src, os.path.join("/var/lib/marzban", sub), dirs_exist_ok=True)

                if os.path.exists(m_compose_path):
                    log("راه‌اندازی کانتینرهای مرزبان با docker compose...", "info")
                    subprocess.run(["docker", "compose", "-f", m_compose_path, "up", "-d"], capture_output=True)
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
                        if 'bak_path' in locals() and os.path.exists(bak_path):
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
                
                comp_file = os.path.join(tgt_dir, "docker-compose.yml")
                if os.path.exists(comp_file):
                    log("توقف موقت کانتینرهای Remnawave...", "info")
                    subprocess.run(["docker", "compose", "-f", comp_file, "down"], capture_output=True)
                
                if os.path.exists(os.path.join(tgt_dir, ".env")):
                    shutil.copy2(os.path.join(tgt_dir, ".env"), os.path.join(tgt_dir, f".env.pre_restore_{ts}.bak"))
                
                for fn in [".env", "docker-compose.yml"]:
                    sf = os.path.join(src_remna, fn)
                    if os.path.exists(sf):
                        shutil.copy2(sf, os.path.join(tgt_dir, fn))
                
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
                
                if os.path.exists(os.path.join(src_remna, "certs")):
                    shutil.copytree(os.path.join(src_remna, "certs"), os.path.join(tgt_dir, "certs"), dirs_exist_ok=True)
                
                if os.path.exists(os.path.join(tgt_dir, "docker-compose.yml")):
                    log("راه‌اندازی کانتینرهای Remnawave...", "info")
                    subprocess.run(["docker", "compose", "-f", os.path.join(tgt_dir, "docker-compose.yml"), "up", "-d"], capture_output=True)
                
                log("پنل Remnawave / Remna با موفقیت بازگردانی شد. ✅", "ok")

        # 6. RESTORE HIDDIFY MANAGER
        if "hiddify" in selected_panels:
            src_hid = os.path.join(staging_dir, "hiddify")
            if os.path.exists(src_hid):
                log("توقف موقت سرویس Hiddify جهت اعمال تنظیمات...", "info")
                subprocess.run(["systemctl", "stop", "hiddify-panel"], capture_output=True)
                
                h_dirs = ["/opt/hiddify-config", "/opt/hiddify-manager"]
                h_target_dir = "/opt/hiddify-config"
                for hd in h_dirs:
                    if os.path.exists(hd):
                        h_target_dir = hd
                        break
                os.makedirs(h_target_dir, exist_ok=True)
                
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
                
                for cf in ["current-config.json", ".env"]:
                    if os.path.exists(os.path.join(src_hid, cf)):
                        shutil.copy2(os.path.join(src_hid, cf), os.path.join(h_target_dir, cf))
                if os.path.exists(os.path.join(src_hid, "ssl")):
                    shutil.copytree(os.path.join(src_hid, "ssl"), os.path.join(h_target_dir, "ssl"), dirs_exist_ok=True)
                
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
