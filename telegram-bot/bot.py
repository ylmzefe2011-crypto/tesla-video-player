import base64
import logging
import os
import re
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import yt_dlp

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "/tmp/videos")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def ensure_user(conn, tg_user) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
            RETURNING id
            """,
            (str(tg_user.id), tg_user.username, tg_user.first_name),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"]


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid if re.match(r"^[A-Za-z0-9_-]{6,15}$", vid) else None
    if "youtube.com" in host:
        for part in parsed.query.split("&"):
            if part.startswith("v="):
                vid = part.split("=", 1)[1]
                return vid if re.match(r"^[A-Za-z0-9_-]{6,15}$", vid) else None
    return None


def prepare_cookies_file() -> str | None:
    cookies_b64 = os.getenv("YOUTUBE_COOKIES_B64")
    cookies_raw = os.getenv("YOUTUBE_COOKIES")
    cookies_path = "/tmp/cookies.txt"

    if cookies_b64:
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        decoded = base64.b64decode(cookies_b64).decode("utf-8", errors="ignore")
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(decoded)
        return cookies_path

    if cookies_raw:
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(cookies_raw)
        return cookies_path

    return None


def download_video_info(url: str) -> dict:
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    cookies_file = prepare_cookies_file()

    ydl_opts = {
        "format": "bv*+ba/b/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(DOWNLOAD_PATH, "%(id)s.%(ext)s"),
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        size = os.path.getsize(filepath) if os.path.exists(filepath) else None
        return {
            "youtube_id": info.get("id") or extract_youtube_id(url),
            "title": info.get("title") or "Untitled Video",
            "thumbnail
