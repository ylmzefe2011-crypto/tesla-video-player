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
        "outtmpl": os.path.join(DOWNLOAD_PATH, "%(id)s.%(ext)s"),
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
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
            "thumbnail_url": info.get("thumbnail"),
            "duration": int(info["duration"]) if info.get("duration") else None,
            "file_size": size,
            "file_url": info.get("url") or url,
        }


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    try:
        conn = get_db_connection()
        ensure_user(conn, update.effective_user)
        conn.close()
    except Exception as exc:
        logger.error("DB error on /start: %s", exc)

    await update.message.reply_text(
        "Tesla Video Player botuna hoş geldin!\n"
        "İndirmek veya kütüphaneye eklemek için bana bir video bağlantısı gönder.\n"
        "Komutlar: /list, /help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Kullanım:\n"
        "• Video URL'si göndererek kütüphaneye kayıt açabilirsin.\n"
        "• /list — Kayıtlı videolarını listeler.\n"
        "• /help — Bu yardım mesajını gösterir."
    )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    try:
        conn = get_db_connection()
        user_id = ensure_user(conn, update.effective_user)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, duration FROM videos WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
                (user_id,),
            )
            rows = cur.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text("Henüz kayıtlı videon yok.")
            return

        lines = [f"{idx + 1}. {r['title']}" for idx, r in enumerate(rows)]
        await update.message.reply_text("Son videoların:\n" + "\n".join(lines))
    except Exception as exc:
        logger.error("DB error on /list: %s", exc)
        await update.message.reply_text("Videolar listelenirken bir hata oluştu.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await update.message.reply_text("Lütfen geçerli bir http/https video bağlantısı gönder.")
        return

    status_msg = await update.message.reply_text("Video işleniyor, lütfen bekle...")

    try:
        conn = get_db_connection()
        user_id = ensure_user(conn, update.effective_user)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO download_queue (user_id, telegram_chat_id, youtube_url, status)
                VALUES (%s, %s, %s, 'downloading')
                RETURNING id
                """,
                (user_id, str(update.effective_chat.id), text),
            )
            queue_id = cur.fetchone()["id"]
            conn.commit()

        meta = download_video_info(text)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO videos (user_id, youtube_id, title, thumbnail_url, duration, file_size, file_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    meta["youtube_id"],
                    meta["title"],
                    meta["thumbnail_url"],
                    meta["duration"],
                    meta["file_size"],
                    meta["file_url"],
                ),
            )
            cur.execute(
                "UPDATE download_queue SET status = 'completed', updated_at = NOW() WHERE id = %s",
                (queue_id,),
            )
            conn.commit()

        conn.close()
        await status_msg.edit_text(f"Tamamlandı: {meta['title']}")
    except Exception as exc:
        logger.error("Video processing failed: %s", exc)
        try:
            if "conn" in locals() and "queue_id" in locals():
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE download_queue SET status = 'failed', error_message = %s, updated_at = NOW() WHERE id = %s",
                        (str(exc)[:500], queue_id),
                    )
                    conn.commit()
                conn.close()
        except Exception:
            pass
        await status_msg.edit_text("Video işlenirken bir hata oluştu.")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot started polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
