import os
import threading
import logging
import urllib.parse
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import OperationalError

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))

app = Flask(__name__)

# Parse DB URL properly
def parse_db_url(url):
    parsed = urllib.parse.urlparse(url)
    return {
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'dbname': parsed.path[1:]
    }

if DATABASE_URL:
    db_params = parse_db_url(DATABASE_URL)
    pool = ThreadedConnectionPool(1, 20, **db_params)
    app.config['DB_POOL'] = pool
    logger.info("DB pool created")
else:
    logger.error("No DATABASE_URL")
    pool = None

def get_db_connection():
    if not pool:
        raise Exception("No DB pool")
    return app.config['DB_POOL'].getconn()

def put_db_connection(conn):
    app.config['DB_POOL'].putconn(conn)

# Init DB
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            coins INTEGER DEFAULT 0
        )
        """)
        conn.commit()
        cur.close()
        put_db_connection(conn)
        logger.info("DB initialized")
    except Exception as e:
        logger.error(f"DB init failed: {e}")

# Bot handlers with error handling
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
        conn.commit()
        cur.close()
        put_db_connection(conn)
        await update.message.reply_text("Welcome! You are registered.")
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("Error occurred. Try again.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE user_id=%s", (user_id,))
        result = cur.fetchone()
        cur.close()
        put_db_connection(conn)
        if result:
            await update.message.reply_text(f"Your balance: {result[0]} coins")
        else:
            await update.message.reply_text("You are not registered. Send /start first.")
    except Exception as e:
        logger.error(f"Balance error: {e}")
        await update.message.reply_text("Error. Send /start.")

# Run bot in NON-daemon thread
def run_bot():
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN")
        return
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("balance", balance))
        logger.info("Bot starting polling...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Bot failed: {e}")

@app.route("/")
def home():
    return "Bot is running! Check logs."

if __name__ == "__main__":
    init_db()
    # Bot in separate NON-daemon thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    logger.info("Flask starting...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
