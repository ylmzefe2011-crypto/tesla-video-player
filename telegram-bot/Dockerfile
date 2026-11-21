FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY telegram-bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY telegram-bot /app/telegram-bot
WORKDIR /app/telegram-bot

CMD ["python", "bot.py"]
