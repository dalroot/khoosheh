# 🔒 Security Policy

## Supported Versions

We actively maintain and provide security patches for the following versions of **Khoosheh**:

| Version | Supported          |
| ------- | ------------------ |
| 2.5.x   | :white_check_mark: |
| 2.4.x   | :white_check_mark: |
| < 2.4   | :x:                |

---

## Reporting a Vulnerability

The security and privacy of users, server administrators, and proxy nodes are paramount. If you discover a security vulnerability or exploit in Khoosheh:

1. **Do NOT open a public issue.**
2. Report privately via GitHub Security Advisories or Telegram:
   - **GitHub Private Vulnerability Reporting**: [Report a vulnerability](https://github.com/dalroot/khoosheh/security/advisories/new)
   - **Telegram Support & Security**: [@dallrep](https://t.me/dallrep)
3. Please include detailed steps to reproduce the issue, proof-of-concept payloads, and affected panel types (e.g. 3X-UI, Marzban, PasarGuard).

### Response SLAs
- **Acknowledgment**: Within 24 hours.
- **Initial Assessment**: Within 48 hours.
- **Hotfix Release**: Within 72 hours for critical issues.

---

## Security Architecture Highlights
- **Zero-Downtime Hot Backups**: Uses SQLite Online WAL Checkpoints (`PRAGMA wal_checkpoint(TRUNCATE)`) to prevent database corruption.
- **Strong Encryption**: Backups are encrypted with **AES-256 (7z)** before transmission.
- **Token-Based Authentication**: Web dashboard uses salted SHA-256 passwords and cryptographically secure tokens.
- **Automated Scanning**: Automated CodeQL SAST static analysis and Dependabot security tracking run on every commit and pull request.
