import os
import threading
import psycopg2
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ENV VARIABLES
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# =========================
# DATABASE CONNECTION
# =========================

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    coins INTEGER DEFAULT 0
)
""")
conn.commit()

# =========================
# TELEGRAM COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
    conn.commit()

    await update.message.reply_text("Welcome! You are registered.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cur.execute("SELECT coins FROM users WHERE user_id=%s", (user_id,))
    result = cur.fetchone()

    if result:
        await update.message.reply_text(f"Your balance: {result[0]} coins")
    else:
        await update.message.reply_text("You are not registered. Send /start first.")

# =========================
# RUN TELEGRAM BOT
# =========================

def run_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))

    application.run_polling()

# =========================
# FLASK APP (For Railway)
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
