# 🌾 Khoosheh (خوشه) — Universal Multi-Panel Backup & Restore Engine

<div align="center">

[![Release](https://img.shields.io/github/v/release/dalroot/khoosheh?color=blue&label=Release&logo=github)](https://github.com/dalroot/khoosheh/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![CI Quality](https://img.shields.io/github/actions/workflow/status/dalroot/khoosheh/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/dalroot/khoosheh/actions)
[![Panels: 3X-UI | Marzban | PasarGuard | Remnawave | Hiddify](https://img.shields.io/badge/Panels-3X--UI%20%7C%20Marzban%20%7C%20PasarGuard%20%7C%20Remna%20%7C%20Hiddify-orange.svg)](#-ماتریکس-پشتیبانی-از-پنلها-supported-panels)

**سامانه جامع، خودکار و هوشمند پشتیبان‌گیری، بازرسی عمیق دیتابیس و مهاجرت/بازگردانی (Smart Restore) انواع پنل‌های مدیریت ترافیک و زیرساخت لینوکس**

[فارسی](#-راهنمای-فارسی) • [English Guide](#-english-guide) • [نصب سریع](#-نصب-سریع-یکخطی-quick-install) • [پنل‌ها](#-ماتریکس-پشتیبانی-از-پنلها-supported-panels) • [مستندات API](#-مستندات-rest-api)

</div>

---

## 📖 راهنمای فارسی

پروژه **«خوشه» (Khoosheh)** یک راهکار مستقل، فوق‌العاده سبک، ماژولار و تمام‌عیار برای پشتیبان‌گیری و بازگردانی خودکار انواع پنل‌های پروکسی و تنظیمات زیرساختی لینوکس است. خوشه به صورت مستقل با پایتون خالص (Pure Python) و بدون نیاز به وب‌سرورهای خارجی، بسته‌های حجیم npm/node یا فریم‌ورک‌های سنگین پیاده‌سازی شده و از یک داشبورد مهندسی‌شده و مدرن مشابه استاندارد ۳X-UI بهره می‌برد.

---

### 🌟 ویژگی‌های کلیدی (Core Features)

- **🛡️ پشتیبان‌گیری آنلاین دیتابیس بدون قطعی (Zero-Downtime Hot Backup):** پشتیبان‌گیری اتمیک از دیتابیس‌های SQLite با صدور فرمان `PRAGMA wal_checkpoint(TRUNCATE)` و استفاده از نیتیو SQLite Online Backup API پایتون؛ تضمین صددرصدی کپی سالم بدون قفل‌شدن جدول‌ها یا توقف سرویس.
- **🔍 بازرسی عمیق دیتابیس بدون نیاز به اجرای پنل (Deep Offline Inspector):** تجزیه و تحلیل ساختار دیتابیس داخل فایل پشتیبان و استخراج تعداد کاربران، کاربران فعال، مصرف ترافیک، پروتکل‌ها، اینباندها و سرتیفیکیت‌ها قبل از بازگردانی.
- **🔄 ویزارد بازگردانی هوشمند و بدون خطا (Smart Restore & Migration Wizard):**
  - تهیه نسخه پشتیبان حفاظتی خودکار (`.pre_restore_<ts>.bak`) پیش از اعمال تغییرات.
  - آزادسازی قفل‌های لینوکس و پاکسازی فایل‌های کش موقت SQLite (`-wal` و `-shm`).
  - اعتبارسنجی یکپارچگی (`PRAGMA integrity_check`) با مکانیزم بازگشت خودکار (Auto-Rollback) در صورت معیوب بودن فایل آرشیو.
  - مدیریت چرخه حیات کانتینرهای داکر و سرویس‌های systemd به صورت خودکار.
- **⚡ پشتیبانی چندمسیره و چندپنله (Universal Multi-Panel Engine):** شناسایی و کشف خودکار پنل‌های **3X-UI** (تمام فورک‌های سنایی، علیرضا، فرانتس‌کافکا، واکسیلو)، **مرزبان (Marzban)**، **پاسارگارد (PasarGuard)**، **رمنا (Remnawave / Remna)**، **هیدیفای (Hiddify Manager)** و تانل‌های شبکه.
- **🎨 طراحی داشبورد مهندسی مطابق استاندارد ۳X-UI:**
  - تفکیک کامل نمودارهای اسپارک‌لاین از اعداد و متون بدون هیچ‌گونه تداخل بصری.
  - نمایش اعداد و شاخص‌ها با فونت استاندارد مهندسی `Inter` و ارقام انگلیسی جدول‌بندی‌شده (`tabular-nums`).
  - پالت‌های رنگی استاندارد تم تاریک (`#0b0f17`) و روشن (`#f0f2f5`).
- **🤖 ربات تعاملی تلگرام:** ارسال خودکار فایل‌های فشرده آرشیو به پی‌وی ادمین، هشدارهای لحظه‌ای، کلیدهای شیشه‌ای درخواست پشتیبان فوری و خلاصه ترافیک مصرفی سرور.
- **🔒 رمزنگاری استاندارد 7z (AES-256):** قابلیت محافظت از آرشیوهای پشتیبان با رمز عبور قدرتمند.
- **💾 ذخیره‌سازی اتمیک پیکربندی (Atomic Config Engine):** جلوگیری از Race Condition و پاک شدن تنظیمات در قطعی‌های ناگهانی برق یا ریستارت سرور.

---

### 🖥️ ماتریکس پشتیبانی از پنل‌ها (Supported Panels)

| نام پنل | مخازن رسمی پشتیبانی‌شده | مسیرهای پایگاه داده و تنظیمات | نوع پشتیبان‌گیری | بازرسی عمیق |
| :--- | :--- | :--- | :--- | :---: |
| **3X-UI / X-UI** | `MHSanaei/3x-ui`<br>`alireza0/x-ui`<br>`FranzKafkaYu/x-ui`<br>`vaxilu/x-ui` | `/etc/x-ui/x-ui.db`<br>`/usr/local/x-ui/bin/x-ui.db`<br>`/opt/x-ui/x-ui.db`<br>`./db/x-ui.db` | SQLite Online + سرتیفیکیت‌های `/etc/x-ui/certs` و `/root/cert` | ✅ |
| **Marzban (مرزبان)** | `Gozargah/Marzban` | `/var/lib/marzban/db.sqlite3`<br>`/opt/marzban/.env`<br>`/opt/marzban/docker-compose.yml` | SQLite Online + دامپ MySQL + تمپلت‌ها و `xray-core` | ✅ |
| **PasarGuard (پاسارگارد)** | `PasarGuard` | `/var/lib/pasarguard/db.sqlite3`<br>`/opt/pasarguard/.env`<br>`/opt/pasarguard/sub_bridge.py` | SQLite Online + کانتینر + سرتیفیکیت نودها `/var/lib/pg-node/certs` | ✅ |
| **Remna / Remnawave** | `remnawave` | `/opt/remnawave/`<br>`/opt/remna/`<br>`database.sqlite`<br>`remnawave-db` (Postgres) | SQLite Online + دامپ کانتینری `pg_dumpall` + `.env` | ✅ |
| **Hiddify Manager** | `hiddify-manager`<br>`hiddify-config` | `/opt/hiddify-config/hiddifypanel/hiddifypanel.db`<br>`/opt/hiddify-manager/...`<br>`current-config.json` | SQLite Online + تنظیمات JSON + کلیدهای `ssl/` | ✅ |
| **Network & Tunnels** | Hawal & Nginx | `/etc/nginx`<br>`/opt/hawal`<br>`/etc/hawal`<br>`/etc/haproxy` | فایل‌های پیکربندی تانل و رورس‌پروکسی | ✅ |
| **مسیر دلخواه (Custom)** | هر نوع اسکریپت یا پنل اختصاصی | مسیر فایل دیتابیس یا پوشه دلخواه کاربر | SQLite / فایل‌ها و دایرکتوری‌ها | ✅ |

---

### 🚀 نصب سریع یک‌خطی (Quick Install)

برای نصب خودکار خوشه روی توزیع‌های اوبونتو یا دبیان:

```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```

پس از اتمام نصب، وب‌پنل روی پورت پیش‌فرض در دسترس خواهد بود:
```text
http://YOUR_SERVER_IP:2099
```
> در اولین ورود، پنجره راه‌اندازی اولیه نمایش داده می‌شود که می‌توانید نام کاربری و رمز عبور دلخواه مدیریت را تنظیم کنید.

---

### 🛠️ دستورات مدیریت سرویس (Service Management)

```bash
# بررسی وضعیت سرویس
sudo systemctl status khoosheh

# راه‌اندازی مجدد
sudo systemctl restart khoosheh

# مشاهده لاگ‌های لحظه‌ای
journalctl -u khoosheh -f --no-pager
```

---

### 📡 مستندات REST API

سامانه خوشه دارای یک API داخلی سریع جهت مانیتورینگ و ادغام در سیستم‌های Devops است:

| متد | مسیر (Endpoint) | توضیحات |
| :--- | :--- | :--- |
| `GET` | `/api/status` | وضعیت لایو سرور، منابع سخت‌افزاری، پنل‌های شناسایی‌شده و لیست بکاپ‌ها |
| `POST` | `/api/backup` | ایجاد فوری یک نسخه پشتیبان رمزنگاری‌شده از کلیه پنل‌ها |
| `POST` | `/api/restore/inspect` | بازگشایی امن آرشیو و تحلیل عمیق متادیتا بدون اعمال روی سرور |
| `POST` | `/api/restore/execute` | اجرای فرآیند بازگردانی پنل‌های انتخاب‌شده با اعتبارسنجی و ریستارت هوشمند |
| `POST` | `/api/restore/upload` | آپلود فایل بکاپ خارجی جهت بازگردانی مستقیم |
| `GET` | `/api/backups/download/<file>` | دانلود ایمن فایل آرشیو بکاپ |

---

## 🌐 English Guide

**Khoosheh** is an autonomous, lightweight, zero-dependency backup and smart restore engine designed specifically for Linux servers and modern proxy management panels.

### Highlights
- **Zero-Downtime Hot Backups**: Native SQLite WAL checkpoints (`PRAGMA wal_checkpoint(TRUNCATE)`) and atomic streaming backups.
- **Deep Database Inspector**: Inspect user counts, active clients, inbounds, traffic usage, protocols, and TLS certificates directly from backup archives before initiating restoration.
- **Automated Smart Restore Engine**: Automated pre-restore rollback snapshots, stale WAL/SHM file cleanup, SQLite integrity validation (`PRAGMA integrity_check`), and seamless container / systemd service orchestration.
- **Multi-Panel Architecture**: Native auto-discovery for **3X-UI** (Sanaei, Alireza, FranzKafkaYu, vaxilu), **Marzban**, **PasarGuard**, **Remnawave**, **Hiddify**, and custom directories.
- **Official 3X-UI Grade UI**: Clean, responsive Ant Design dashboard featuring isolated sparklines, tabular numbers, and connection statistics in Dark & Light palettes.
- **Interactive Telegram Bot**: Automated backup distribution, AES-256 encryption, and instant on-demand backups via inline keyboard.

### Quick Start
```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```

Access the web interface at:
```text
http://YOUR_SERVER_IP:2099
```

---

## 📄 لایسنس (License)

این پروژه تحت لایسنس بین‌المللی [MIT](LICENSE) به صورت متن‌باز منتشر شده است.
