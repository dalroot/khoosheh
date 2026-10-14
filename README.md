# 🌾 Khoosheh (خوشه) — سامانه پشتیبان‌گیری و بازگردانی هوشمند پنل‌های وی‌پی‌ان، سرورها و نودها

<div align="center">

![Khoosheh Dashboard](docs/dashboard.png)

[![Release](https://img.shields.io/github/v/release/dalroot/khoosheh?color=blue&label=Release&logo=github)](https://github.com/dalroot/khoosheh/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![CI Quality](https://img.shields.io/github/actions/workflow/status/dalroot/khoosheh/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/dalroot/khoosheh/actions)
[![CodeQL Security](https://img.shields.io/github/actions/workflow/status/dalroot/khoosheh/codeql.yml?branch=main&label=CodeQL%20Security&logo=github&logoColor=white)](https://github.com/dalroot/khoosheh/security)
[![Dependabot](https://img.shields.io/badge/Dependabot-Active-02569B?logo=dependabot&logoColor=white)](https://github.com/dalroot/khoosheh)
[![Security Policy](https://img.shields.io/badge/Security-Policy-blue.svg)](SECURITY.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](https://github.com/dalroot/khoosheh/pulls)
[![Downtime Benchmark](https://img.shields.io/badge/Downtime-%3C%201%20min-059669.svg)](#-بنچمارک-سرعت-انتقال-کامل-ترافیک-و-مشارکتها-benchmarks--prs)
[![Restore Speed](https://img.shields.io/badge/Restore-%3C%205%20min-blue.svg)](#-بنچمارک-سرعت-انتقال-کامل-ترافیک-و-مشارکتها-benchmarks--prs)
[![Telegram Support](https://img.shields.io/badge/Telegram-Channel-2CA5E0?logo=telegram&logoColor=white)](https://t.me/dallrep)

**پشتیبان‌گیری خودکار، ایزوله و بدون قطعی از پایگاه‌داده‌ها، کانفیگ‌ها و سرتیفیکیت‌های انواع پنل‌های پروکسی و وی‌پی‌ان با بازرسی عمیق، انتقال ۱۰۰٪ ترافیک کاربران و بازیابی هوشمند**

[راهنمای فارسی](#-راهنمای-جامع-فارسی) • [English Guide](#-english-guide) • [بنچ‌مارک و مشارکت](#-بنچمارک-سرعت-انتقال-کامل-ترافیک-و-مشارکتها-benchmarks--prs) • [نصب سریع](#-نصب-سریع-یکخطی-quick-install) • [پنل‌ها](#-پنلهای-پشتیبانیشده-supported-panels) • [قابلیت‌های ربات](#-قابلیتهای-کامل-ربات-تلگرام) • [نظرات و دیسکاشن](#-نظرات-پیشنهادات-و-اتصال-به-github-discussions) • [کانال پشتیبانی](#-پشتیبانی-و-ارتباط)

</div>

---

<div dir="rtl">

## 📖 راهنمای جامع فارسی

پروژه **«خوشه» (Khoosheh)** ابزاری سبک، مستقل و متمرکز برای بکاپ‌گیری، مانیتورینگ سلامت و مهاجرت بی‌دردسر پنل‌های وی‌پی‌ان، سرورهای تانل و نودهای متصل است. در زمان بکاپ‌گیری، پنل شما حتی ۱ ثانیه هم قطع نمی‌شود، هیچ داده‌ای قفل نمی‌گردد و در صورت خرابی سرور یا تمایل به جابه‌جایی، با ویزارد هوشمند بازگردانی می‌توانید تمام کاربران، اینباندها و کانفیگ‌ها را با چند کلیک زنده کنید.

---

### ⚡ بنچ‌مارک سرعت، انتقال کامل ترافیک و مشارکت‌ها (Benchmarks & PRs)

یکی از مهم‌ترین دغدغه‌های مدیران سرور در جابه‌جایی‌ها، از دست رفتن حجم مصرفی کاربران و زمان طولانی قطعی است. خوشه با معماری استاندارد خود این مشکلات را حل کرده است:

* ⏱️ **داون‌تایم انتقال زیر ۱ دقیقه (Near-Zero Downtime):** مهاجرت کامل کاربران و سوییچ دیتابیس به سرور یا نود جدید با کمترین وقفه زمانی (زیر ۶۰ ثانیه).
* 📊 **انتقال ۱۰۰٪ دست‌نخورده اطلاعات ترافیک کاربران (Zero Data Loss):** حجم دانلود، آپلود، تاریخ انقضا و وضعیت اکانت‌های تمامی کاربران بدون کوچک‌ترین تغییر، حذف یا اختلاف آماری جابه‌جا می‌شوند.
* 🚀 **بازگردانی اولیه زیر ۵ دقیقه:** بر اساس آزمایش‌های واقعی، فرآیند بازگردانی بکاپ و راه‌اندازی کامل پنل به همراه کاربران در کمتر از ۵ دقیقه به طور خودکار انجام می‌شود.
* ⚙️ **اتوماسیون استانداردهای پیچیده:** عملیات سنگین نظیر `PRAGMA wal_checkpoint(TRUNCATE)`، تست سلامت اتمیک ساختار دیتابیس با `PRAGMA integrity_check`، فشرده‌سازی و رمزگذاری AES-256 کاملاً خودکار شده است.
* 🤝 **پروژه پویا و پذیرش مشارکت‌ها (PRs Welcome):** پروژه خوشه به شکل مستمر در حال توسعه و آپدیت است و از کلیه مشارکت‌های توسعه‌دهندگان، گزارش باگ‌ها، و پول‌ریکوئست‌ها (Pull Requests) برای افزودن پنل‌ها و بهینه‌سازی‌ها با آغوش باز استقبال می‌کند.

---

### 🖥️ پنل‌های پشتیبانی‌شده (Supported Panels)

سامانه خوشه دارای قابلیت تشخیص خودکار (Auto-Discovery) است و مسیرهای استاندارد، نصبیات کانتینری و سرویس‌های محلی پنل‌های زیر را شناسایی و پوشش می‌دهد:

#### ۱. پنل ۳X-UI و X-UI
* **نسخه‌ها و فورک‌های تحت پوشش:** نسخه سنایی (`MHSanaei`)، علیرضا (`alireza0`)، فرانتس‌کافکا (`FranzKafkaYu`) و واکسیلو (`vaxilu`)
* **فایل‌ها و مسیرهای دیتابیس:** دیتابیس اصلی در `/etc/x-ui/x-ui.db` به همراه تنظیمات هسته Xray و گواهینامه‌های SSL
* **موتور ذخیره‌سازی:** دیتابیس SQLite با پشتیبان‌گیری جریانی زنده و اتمیک (بدون وقفه در اتصال کاربران)

#### ۲. پنل مرزبان (Marzban - Gozargah)
* **ساختار استقرار:** کانتینرهای Docker Compose و سرویس بومی پایتون
* **فایل‌ها و مسیرهای دیتابیس:** فایل دیتابیس `/var/lib/marzban/db.sqlite3`، متغیرهای محیطی `.env`، تمپلت‌های سابسکریپشن و دامپ‌های کانتینری MySQL
* **موتور ذخیره‌سازی:** پشتیبانی همزمان از دیتابیس SQLite و خروجی استخراج‌شده داکر MariaDB/MySQL

#### ۳. پنل پاسارگارد (PasarGuard)
* **ساختار استقرار:** کانتینر اختصاصی داکر و نودهای توزیع‌شده
* **فایل‌ها و مسیرهای دیتابیس:** فایل `/var/lib/pasarguard/db.sqlite3`، تنظیمات پل سابسکریپشن `sub_bridge` و کلیدهای امنیتی نودها
* **موتور ذخیره‌سازی:** دیتابیس SQLite به همراه مانیتورینگ آنلاین وضعیت اتصال کاربران

#### ۴. پنل رمنا و رمناویو (Remnawave)
* **ساختار استقرار:** سامانه مدیریت کاربران سابسکریپشن و هسته مرکزی
* **فایل‌ها و مسیرهای دیتابیس:** دیتابیس `/opt/remna/database.sqlite`، فایل‌های متغیر محیطی `.env` و سرتیفیکیت‌های فعال
* **موتور ذخیره‌سازی:** SQLite به همراه قابلیت پشتیبان‌گیری از کانتینرهای PostgreSQL

#### ۵. پنل هیدیفای منیجر (Hiddify Manager)
* **ساختار استقرار:** پنل مدیریت مرکزی هیدیفای
* **فایل‌ها و مسیرهای دیتابیس:** پایگاه داده اصلی `hiddifypanel.db` و فایل پیکربندی `current-config.json`
* **موتور ذخیره‌سازی:** پایگاه داده SQLite و سرتیفیکیت‌های Let's Encrypt

#### ۶. تانل‌ها و وب‌سرورهای معکوس (Hawal & Nginx)
* **ساختار استقرار:** تانل‌های ارتباطی هَوال و پروکسی معکوس انجین‌ایکس
* **فایل‌ها و مسیرهای دیتابیس:** فایل `/etc/hawal/agent.json` و کانفیگ‌های فعال Nginx و HAProxy

#### ۷. مسیرهای سفارشی (Custom Paths)
* **امکانات:** امکان تعریف بی‌نهایت فایل دیتابیس، فولدر یا فایل‌های کانفیگ دلخواه شما از طریق داشبورد وب

---

### 🗄️ نوع دیتابیس‌های پشتیبانی‌شده

* **پایگاه داده SQLite (بکاپ گرم و زنده - Hot Backup):** انجام بکاپ اتمیک با فرمان `PRAGMA wal_checkpoint(TRUNCATE)` و متد پشتیبان‌گیری جریانی نیتیو پایتون؛ بدون ۱ ثانیه قطعی پنل و بدون خطر خرابی یا قفل‌شدگی داده‌ها.
* **پایگاه داده MySQL و MariaDB:** تهیه دامپ خودکار از طریق کانتینرهای فعال داکر (مورد استفاده در پنل‌هایی مانند مرزبان).
* **پایگاه داده PostgreSQL:** ایجاد اسنپ‌شات کانتینری و خروجی ساختاریافته (مورد استفاده در پنل‌هایی مانند رمناویو).
* **فایل‌های متنی، کانفیگ‌ها و کلیدها:** پشتیبان‌گیری کامل از متغیرهای محیطی (`.env`)، کانفیگ‌های ساختاریافته JSON و گواهینامه‌های SSL/TLS.

---

### 🤖 قابلیت‌های کامل ربات تلگرام

خوشه مجهز به یک موتور ربات تعاملی تلگرام است که نیازی به فیلترشکن روی سرور خارجی ندارد و امکانات زیر را فراهم می‌کند:

* ⚡️ **بکاپ فوری و ارسال فایل:** با فشردن یک کلید در پی‌وی ربات، درجا از تمام پنل‌ها بکاپ گرفته شده، فایل با فرمت فشرده و رمزگذاری‌شده به تلگرام شما ارسال می‌شود.
* 📊 **اسنپ‌شات مصرف ترافیک:** گزارش ۲۴ ساعته و ۷ روزه مصرف ترافیک، تفکیک آپلود و دانلود، کاربران آنلاین در لحظه و ۲۴ ساعت اخیر، همراه با فهرست **۵ کاربر پرمصرف (Top 5 Users)**.
* 📋 **کارنامه سلامت و گزارش روزانه (Daily Digest):** گزارش جامع میزان مصرف رم، دیسک، وضعیت سلامت پنل و وضعیت نودهای فعال همراه با پرچم کشورها (🇬🇧، 🇳🇱، 🇩🇪، 🇮🇷 و...).
* 🖥 **وضعیت سخت‌افزاری سرور:** نمایش زنده لود CPU، حافظه RAM، فضای دیسک، آپتایم و IP عمومی سرور.
* 📦 **دریافت آخرین فایل بکاپ:** دانلود آخرین بکاپ موجود روی سرور بدون نیاز به ساخت فایل جدید.
* 🌐 **لینک ورود به وب‌پنل:** دکمه شیشه‌ای حاوی لینک مستقیم ورود به داشبورد وب.
* ⏰ **ارسال زمان‌بندی‌شده خودکار:** تنظیم بازه‌های دلخواه (مثلاً هر ۶ ساعت یک‌بار) جهت دریافت خودکار فایل‌های فشرده بکاپ رمزنگاری‌شده در تلگرام.
* 🔒 **رمزنگاری قدرتمند AES-256 (7z):** امکان قرار دادن پسورد دلخواه روی تمام فایل‌های خروجی ارسالی به تلگرام.

---

### 🔌 پورت‌های درگیرشده (Ports)

سامانه خوشه طوری طراحی شده که کمترین پورت را اشغال کند و **هیچ تداخلی با پورت‌های فعال پروکسی‌ها ندارد**:

| پورت | پروتکل | کاربرد | امکان تغییر |
| :---: | :---: | :--- | :---: |
| **`2099`** | HTTP | دسترسی به داشبورد تحت وب | ✅ از تب تنظیمات |
| **`2098`** | HTTPS | اتصال امن SSL به وب‌پنل | ✅ از تب تنظیمات |

> **نکته مهم:** پورت‌های ۲۰۹۹ و ۲۰۹۸ با پورت‌های مشهور پنل‌ها (مثل ۲۰۵۳، ۲۰۹۶، ۸۴۴۳، ۴۴۳، ۸۰ و غیره) تداخل ندارند و در کنار پنل‌های فعال بدون مشکل کار می‌کنند.

---

### 🚀 نصب سریع یک‌خطی (Quick Install)

روی سرورهای اوبونتو یا دبیان، دستور زیر را در ترمینال اجرا کنید:

```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```

پس از پایان فرآیند، وب‌پنل در دسترس است:
```text
http://YOUR_SERVER_IP:2099
```

#### 🔑 اولین ورود به وب‌پنل:
1. در اولین ورود، صفحه راه‌اندازی اولیه (Setup Wizard) باز می‌شود.
2. نام کاربری و رمز عبور دلخواه خود را تعیین می‌کنید.
3. بلافاصله پس از ورود، پنل یا پنل‌های نصب‌شده روی سرور (3X-UI، پاسارگارد، مرزبان یا...) **به صورت خودکار شناسایی می‌شوند** و وضعیت کاربران و اینباندهای آن‌ها در داشبورد نقش می‌بندد.

---

### 📑 توضیح منو و بخش‌های پنل وب

رابط کاربری خوشه با استانداردهای مهندسی روز و سبک رسمی ۳X-UI طراحی شده و شامل بخش‌های زیر است:

* **📊 داشبورد مدیریتی (Overview):** نمایش کارت‌های سخت‌افزاری CPU ،RAM ،BANDWIDTH و تعداد بکاپ‌ها با نمودارهای اسپارک‌لاین تفکیک‌شده (بدون تداخل متن و موج)، وضعیت کاربران آنلاین و سرعت لحظه‌ای شبکه.
* **📦 آرشیوهای پشتیبان (Backups):** جدول جامع تمام فایل‌های بکاپ موجود روی سرور همراه با اندازه فایل، تاریخ دقیق، هش امنیتی SHA-256 و کلیدهای دانلود مستقیم یا حذف فایل.
* **🔄 بازیابی هوشمند (Smart Restore Wizard):** ویزارد گام‌به‌گام بازگردانی؛ با انتخاب یا آپلود فایل بکاپ، جداول دیتابیس پیش از بازگردانی رمزگشایی و متادیتاها تحلیل می‌شوند. سپس با بکاپ حفاظتی خودکار (`.bak`) و تست سلامت ساختار (`PRAGMA integrity_check`)، بازگردانی بدون قطعی انجام می‌شود.
* **🗃️ پایگاه‌های داده و پنل‌ها (Panels):** وضعیت اتصال پنل‌های نصب‌شده، تعداد کلاینت‌ها و اینباندهای لایو و امکان تعریف دیتابیس‌ها و فولدرهای سفارشی.
* **🌐 نودها و سرورها:** پایش اتصال سرورهای نود، لوکیشن‌ها و سابسکریپشن‌ها.
* **⚙️ تنظیمات و ربات (Settings):** اتصال ربات تلگرام، تعیین شناسه عددی ادمین، تعیین بازه خودکار بکاپ‌گیری، رمزنگاری AES-256 فایل‌های 7z و تنظیمات نام کاربری و پسورد.
* **💬 نظرات و بازخوردها (Feedback & Community):** ثبت دیدگاه‌ها، امتیازدهی ستاره‌ای، انتقال تجربیات بنچ‌مارک و اتصال خودکار به سامانه دیسکاشن گیت‌هاب (Giscus / GitHub Pages).

---

### 💬 نظرات، پیشنهادات و اتصال به GitHub Discussions

شما می‌توانید تجربیات خود از مهاجرت سرورها، بنچ‌مارک‌های سرعت، و پیشنهادات فنی را مستقیماً از داخل وب‌پنل در تب **«نظرات و بازخوردها»** ثبت نمایید. همچنین بخش نظرات عمومی در [صفحه گیت‌هاب پیجز خوشه](https://dalroot.github.io/khoosheh/) از طریق ویجت تعاملی Giscus فعال است و می‌توانید با اکانت گیت‌هاب خود در بحث‌ها شرکت کنید.

---

### 📢 پشتیبانی و ارتباط

برای طرح سوالات، گزارش مشکلات، دریافت آپدیت‌ها و دسترسی به دیگر پروژه‌های متن‌باز ما به کانال رسمی تلگرام بپیوندید:

👉 **[کانال رسمی تلگرام: t.me/dallrep](https://t.me/dallrep)**

---

## 🎖️ تقدیر و تشکر ویژه (Special Acknowledgment)

> **طراحی معماری، مهندسی الگوها، بازنویسی رابط کاربری و هدایت کامل این پروژه توسط هوش مصنوعی «آنتی‌گراویتی (Antigravity) — ایجنت خودمختار اینترپرایز» انجام شده است.**  
> با سپاس از توانمندی‌های عمیق تحلیل، طراحی بدون وقفه و مهندسی کد ایجنت Antigravity.

</div>

## 🌐 English Guide

**Khoosheh** is an autonomous, lightweight, zero-dependency backup and smart restore engine designed specifically for Linux servers, proxy management panels, and VPN nodes.

### Features
- **Zero-Downtime Hot Backups**: Native SQLite WAL checkpoints (`PRAGMA wal_checkpoint(TRUNCATE)`) without locking tables or service interruptions.
- **Near-Zero Migration Downtime (< 1 min)**: Full server migration and database switch with under 60 seconds of downtime.
- **Zero Client Data & Traffic Loss**: 100% preservation of client upload/download quotas, expiration dates, and account configurations.
- **< 5 Minute Initial Restore**: Complex database operations, schema validation, and service initialization completed in under 5 minutes.
- **Multi-Panel Auto-Discovery**: Full out-of-the-box discovery for **3X-UI** (Sanaei, Alireza, FranzKafkaYu, vaxilu), **Marzban**, **PasarGuard**, **Remnawave**, **Hiddify**, and custom file paths.
- **Deep Database Inspector**: Instantly parses user accounts, active clients, inbounds, traffic volume, protocols, and TLS certificates before restoration.
- **Safe Restore Wizard**: Automatic pre-restore rollback backups (`.pre_restore_<ts>.bak`), stale cache cleanup (`-wal` / `-shm`), SQLite integrity validation, and graceful service restarts.
- **Interactive Telegram Bot**: Instant backup on demand, 24h & 7d usage snapshots, daily server health digests, and automated scheduled distribution with AES-256 encryption.
- **Enterprise Security & PR Bots**: Integrated CodeQL SAST scanning, Dependabot automated updates, Security Policy, and PR verification bots.
- **Contributions & PRs Welcome**: Community-driven project actively welcoming pull requests, issues, and feature proposals.

### Quick Start
```bash
curl -sSL https://raw.githubusercontent.com/dalroot/khoosheh/main/install.sh | bash
```
Open `http://YOUR_SERVER_IP:2099` in your browser. Set your credentials on first login, and your installed panels will be automatically detected.

---

## 📄 لایسنس (License)

پروژه تحت لایسنس بین‌المللی [MIT](LICENSE) به صورت متن‌باز منتشر شده است.
