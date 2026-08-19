import os
import re
import json
import time
import uuid
import shutil
import threading
import subprocess
from pathlib import Path

import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "49"))
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/tmp/igbot"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Optional: comma-separated Telegram chat IDs.
# Leave empty to allow any group where the bot is present.
ALLOWED_CHAT_IDS = {
    x.strip() for x in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if x.strip()
}

app = Flask(__name__)

TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/"
    r"(?:p|reel|reels|tv|share)/[^\s]+",
    re.IGNORECASE,
)


def tg(method, **kwargs):
    r = requests.post(f"{TG}/{method}", data=kwargs, timeout=30)
    r.raise_for_status()
    return r.json()


def tg_json(method, payload):
    r = requests.post(f"{TG}/{method}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def send_text(chat_id, text, reply_to=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_to:
        payload["reply_parameters"] = json.dumps({"message_id": reply_to})
    return tg("sendMessage", **payload)


def safe_chat_allowed(chat_id):
    if not ALLOWED_CHAT_IDS:
        return True
    return str(chat_id) in ALLOWED_CHAT_IDS


def extract_instagram_url(text):
    if not text:
        return None
    m = INSTAGRAM_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(".,!?)>]\"'")


def run_ytdlp(url, workdir):
    # Public Instagram URLs are supported. Private/login-required content
    # needs an authenticated cookie file and is intentionally not configured here.
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--ignore-errors",
        "--no-playlist",
        "--restrict-filenames",
        "--output", str(workdir / "%(playlist_index)03d_%(id)s.%(ext)s"),
        "--merge-output-format", "mp4",
        "--max-filesize", f"{MAX_FILE_MB}M",
        url,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def media_files(workdir):
    allowed = {".mp4", ".mkv", ".webm", ".mov", ".jpg", ".jpeg", ".png", ".webp"}
    return sorted(
        p for p in workdir.iterdir()
        if p.is_file() and p.suffix.lower() in allowed
    )


def send_media(chat_id, path, caption=None):
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        return False, f"{path.name} is {size_mb:.1f} MB, above the configured limit."

    ext = path.suffix.lower()
    method = "sendVideo" if ext in {".mp4", ".mkv", ".webm", ".mov"} else "sendPhoto"

    with path.open("rb") as f:
        files = {"video" if method == "sendVideo" else "photo": f}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption[:1024]
        r = requests.post(f"{TG}/{method}", data=data, files=files, timeout=120)
        if not r.ok:
            return False, r.text[:500]
    return True, None


def process_url(chat_id, url, reply_to):
    workdir = DOWNLOAD_DIR / uuid.uuid4().hex
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        send_text(chat_id, "⏳ دارم محتوا رو می‌گیرم…", reply_to)

        result = run_ytdlp(url, workdir)
        files = media_files(workdir)

        if not files:
            details = (result.stderr or result.stdout or "").strip()
            send_text(
                chat_id,
                "❌ نتونستم محتوای این لینک رو دریافت کنم.\n"
                "ممکنه پست خصوصی، حذف‌شده، محدود، یا نیازمند لاگین باشه.",
                reply_to,
            )
            if details:
                print(details[-3000:])
            return

        sent = 0
        for p in files:
            ok, err = send_media(chat_id, p)
            if ok:
                sent += 1
            else:
                send_text(chat_id, f"⚠️ ارسال {p.name} انجام نشد.\n{err}")

        if sent:
            send_text(chat_id, f"✅ انجام شد — {sent} فایل ارسال شد.")

    except subprocess.TimeoutExpired:
        send_text(chat_id, "❌ دانلود بیشتر از حد مجاز طول کشید و متوقف شد.", reply_to)
    except Exception as e:
        print("ERROR:", repr(e))
        send_text(chat_id, "❌ یه خطای غیرمنتظره رخ داد.", reply_to)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def handle_update(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if chat_id is None or not safe_chat_allowed(chat_id):
        return

    if text.startswith("/start"):
        send_text(
            chat_id,
            "سلام 👋\n"
            "لینک عمومی پست / ریل اینستاگرام رو بفرست تا محتواشو برات بفرستم.\n\n"
            "برای دیدن Chat ID هم /id رو بزن."
        )
        return

    if text.startswith("/id"):
        send_text(chat_id, f"Chat ID: {chat_id}")
        return

    url = extract_instagram_url(text)
    if not url:
        return

    # Avoid duplicate processing from edited messages.
    threading.Thread(
        target=process_url,
        args=(chat_id, url, msg.get("message_id")),
        daemon=True,
    ).start()


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "instagram-telegram-bot"})


@app.post("/telegram/webhook")
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return "forbidden", 403

    update = request.get_json(silent=True) or {}
    threading.Thread(target=handle_update, args=(update,), daemon=True).start()
    return "ok", 200


if __name__ == "__main__":
    # Local development only. Production should use gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
