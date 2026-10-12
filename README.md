# 🌾 Khoosheh (خوشه) — Universal Multi-Panel Backup & Restore Engine

<div align="center">

![Khoosheh Banner](https://raw.githubusercontent.com/dalroot/khoosheh/main/docs/banner.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://www.python.org/)
[![Panels: PasarGuard | 3X--UI | Marzban | Hiddify](https://img.shields.io/badge/Panels-PasarGuard%20%7C%203X--UI%20%7C%20Marzban%20%7C%20Hiddify-orange.svg)](#supported-panels)

**سامانه جامع، خودکار و هوشمند پشتیبان‌گیری، بازرسی عمیق دیتابیس و بازگردانی (Restore) برای پنل‌های مدیریت ترافیک و سرورها**

[فارسی](#راهنمای-فارسی) • [English](#english-guide) • [نصب سریع](#نصب-سریع-یکخطی) • [امکانات](#ویژگیهای-کلیدی)

</div>

---

## راهنمای فارسی

پروژه **«خوشه» (Khoosheh)** یک راهکار مستقل، سبک و همه‌منظوره برای پشتیبان‌گیری و بازگردانی خودکار انواع پنل‌های پروکسی و تنظیمات زیرساختی لینوکس است. خوشه به صورت مستقل با زبان پایتون ۳ بدون نیاز به وابستگی‌های سنگین پیاده‌سازی شده و دارای یک وب‌پنل مدرن (Ant Design) و ربات هوشمند تلگرام است.

### 🌟 ویژگی‌های کلیدی
- **🛡️ پشتیبان‌گیری آنلاین دیتابیس بدون قطعی (Zero-Downtime Hot Backup):** پشتیبان‌گیری اتمیک از پایگاه‌های داده SQLite با استفاده از `PRAGMA wal_checkpoint(TRUNCATE)` و SQLite Backup API؛ بدون توقف سرویس و بدون خطر آسیب به دیتابیس‌های فعال.
- **🔍 بازرسی عمیق دیتابیس (Deep Database Inspection):** استخراج خودکار تعداد کاربران، کاربران فعال، میزان مصرف ترافیک، اینباندها، نودها و گروه‌ها بدون باز کردن دستی دیتابیس.
- **⚡ پشتیبانی چندپنله (Multi-Panel Support):** شناسایی و پشتیبان‌گیری از **PasarGuard (پاسارگارد)**، **3X-UI**، **مرزبان (Marzban)**، **هیدیفای (Hiddify)**، تانل‌های **هَوال (Hawal)** و تنظیمات Nginx و مسیرهای سفارشی.
- **🤖 ربات هوشمند تلگرام:** ارسال دوره‌ای فایل‌های فشرده بکاپ به همراه آمار ترافیک، کاربران پرمصرف، وضعیت سرور و امکان درخواست فوری فایل بکاپ با کلیدهای شیشه‌ای.
- **🔒 رمزنگاری استاندارد 7z (AES-256):** قابلیت محافظت از آرشیوهای پشتیبان با رمز عبور قدرتمند.
- **📊 وب‌پنل سبک و مستقل:** رابط کاربری واکنش‌گرا با پشتیبانی از تم تاریک/روشن، ویزارد بازگردانی گام‌به‌گام (Restore Wizard) و بدون نیاز به نصب npm/node یا وب‌سرور خارجی.
- **💾 مکانیزم ذخیره‌سازی اتمیک تنظیمات:** تضمین پایداری رمزهای عبور و سشن‌ها بدون ریست شدن یا فراموشی نشست‌ها.

---

### 🖥️ پنل‌های پشتیبانی‌شده

| پنل / سرویس | مسیر دیتابیس | نوع پشتیبان‌گیری | بازرسی هوشمند |
| :--- | :--- | :--- | :---: |
| **PasarGuard (پاسارگارد)** | `/var/lib/pasarguard/db.sqlite3` + کانتینر `/opt/pasarguard` | SQLite Online + Compose + Certs | ✅ |
| **3X-UI (Sanaei / Alireza)** | `/etc/x-ui/x-ui.db` | SQLite Online + Certs | ✅ |
| **Marzban (مرزبان)** | `/var/lib/marzban/db.sqlite3` | SQLite Online + `.env` | ✅ |
| **Hiddify Manager (هیدیفای)** | `/opt/hiddify-manager/...` | SQLite Online + Config | ✅ |
| **شبکه و تانل‌ها (Hawal / Nginx)** | `/etc/hawal/` و `/etc/nginx/` | Config Files + Tunnels | ✅ |
| **مسیر سفارشی (Custom)** | هر مسیر فایل یا دایرکتوری دلخواه | Custom Path Engine | ✅ |

---

### 🚀 نصب سریع یک‌خطی

برای نصب خودکار خوشه روی انواع توزیع‌های اوبونتو و دبیان:

```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```

پس از اتمام نصب، وب‌پنل روی آدرس زیر در دسترس خواهد بود:
```text
http://YOUR_SERVER_IP:2099
```
> در اولین ورود به وب‌پنل، پنجره راه‌اندازی اولیه باز می‌شود و می‌توانید نام کاربری و رمز عبور دلخواه خود را تعیین کنید.

---

### 🛠️ نصب دستی (Manual Installation)

اگر مایلید خوشه را مرحله‌به‌مرحله به صورت دستی نصب و پیکربندی کنید:

```bash
# ۱. نصب پیش‌نیازها
sudo apt-get update && sudo apt-get install -y python3 p7zip-full sqlite3 curl

# ۲. ایجاد مسیرها
sudo mkdir -p /opt/khoosheh /var/backups/khoosheh
cd /opt/khoosheh

# ۳. دانلود سورس‌کد
sudo curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/server.py -o /opt/khoosheh/server.py
sudo curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/config.example.json -o /opt/khoosheh/config.json
sudo curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/khoosheh.service -o /etc/systemd/system/khoosheh.service

# ۴. تنظیم دسترسی‌ها
sudo chmod +x /opt/khoosheh/server.py
sudo chmod 600 /opt/khoosheh/config.json

# ۵. راه‌اندازی سرویس
sudo systemctl daemon-reload
sudo systemctl enable --now khoosheh
```

---

### ⚙️ تنظیم ربات تلگرام

برای دریافت خودکار فایل‌های بکاپ در تلگرام:
1. در پنل وب وارد تب **«تنظیمات سیستم»** شوید.
2. توکن ربات تلگرام (`bot_token`) دریافتی از BotFather را وارد کنید.
3. شناسه عددی تلگرام خود (`admin_chat_id`) دریافتی از userinfobot را ثبت نمایید.
4. دکمه **«تست اتصال تلگرام»** را بزنید تا پیام تایید در پی‌وی ربات ارسال شود.

---

### 📂 ساختار اسنپ‌شات پاسارگاد (PasarGuard Snapshot Spec)

بکاپ اختصاصی پاسارگاد شامل اجزای زیر به صورت کاملاً ایزوله است:
1. `pasarguard/db.sqlite3` — دیتابیس تثبیت‌شده کاربران، اینباندها و لاگ‌ها (WAL Checkpoint شده)
2. `pasarguard/.env` — مقادیر محیطی و کلیدهای امنیتی پنل
3. `pasarguard/docker-compose.yml` — تعریف سرویس‌های داکر
4. `pasarguard/sub_bridge.py` — پل سابسکریپشن کلاینت‌ها (در صورت وجود)
5. `pasarguard/certs/` — گواهینامه‌های SSL دامنه

---

## English Guide

**Khoosheh** is an autonomous, lightweight backup and restore system designed for Linux servers and proxy management panels (PasarGuard, 3X-UI, Marzban, Hiddify).

### Quick Install
```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```

### Features
- Native support for SQLite WAL checkpoints and non-blocking online backups
- PasarGuard container & volume automatic discovery
- Integrated Ant Design React Web Interface
- Real-time Telegram alerts and scheduled archive distribution
- Built-in AES-256 encryption using 7z
- Atomic and race-condition free configuration storage

---

## لایسنس (License)
پروژه تحت لایسنس [MIT](LICENSE) به صورت متن‌باز منتشر شده است.
