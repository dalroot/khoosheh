"""
Archive Creation & 7z AES-256 Encryption Engine for Khoosheh
"""
import os
import secrets
import string
import time
import shutil
import tarfile
import subprocess
import hashlib
from datetime import datetime

def generate_strong_password():
    p1 = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    p2 = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"Khoosheh-{p1}-{p2}"

def create_archive_package(staging_dir, backup_dir, base_name, password=""):
    os.makedirs(backup_dir, exist_ok=True)
    tar_path = os.path.join(backup_dir, f"{base_name}.tar.gz")
    
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(staging_dir, arcname="")

    final_path = tar_path
    is_encrypted = False

    if password:
        enc_7z = os.path.join(backup_dir, f"{base_name}.7z")
        cmd = ["7z", "a", f"-p{password}", "-mhe=on", "-y", enc_7z, tar_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
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

    return {
        "final_path": final_path,
        "is_encrypted": is_encrypted,
        "size_mb": size_mb,
        "sha256": digest
    }
