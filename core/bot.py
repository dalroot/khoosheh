"""
Interactive Telegram Bot Engine for Khoosheh
Sends automated encrypted archives, status updates, and handles inline button callbacks.
"""
import urllib.request
import json
import secrets
import os

def tg_api(method, data=None, token=None):
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        body = json.dumps(data).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def send_document_to_telegram(chat_id, file_path, caption="", token=None):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        boundary = "----WebKitFormBoundary" + secrets.token_hex(8)
        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            file_data = f.read()

        body = []
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode())
        body.append(b"")
        body.append(str(chat_id).encode())

        if caption:
            body.append(f"--{boundary}".encode())
            body.append(f'Content-Disposition: form-data; name="caption"'.encode())
            body.append(b"")
            body.append(caption.encode("utf-8"))

        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode())
        body.append(b"Content-Type: application/octet-stream")
        body.append(b"")
        body.append(file_data)
        body.append(f"--{boundary}--".encode())
        body.append(b"")

        payload = b"\r\n".join(body)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(payload))
        }

        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data.get("ok", False)
    except Exception:
        return False
