import os
import urllib.parse
import logging
from flask import Flask, request
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))

# Database setup
pool = None
if DATABASE_URL:
    result = urllib.parse.urlparse(DATABASE_URL)
    db_params = {
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432,
        'dbname': result.path[1:]
    }
    pool = SimpleConnectionPool(1, 10, **db_params)
    logger.info("✅ Database pool created")
else:
    logger.error("❌ DATABASE_URL missing!")

# Bot application (global)
application = None
bot = None

async def start(update: Update, context):
    """Handle /start command"""
    try:
        user_id = update.effective_user.id
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
        conn.commit()
        cur.close()
        pool.putconn(conn)
        await update.message.reply_text("✅ Welcome! Use /balance")
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("❌ Error occurred")

async def balance(update: Update, context):
    """Handle /balance command"""
    try:
        user_id = update.effective_user.id
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        pool.putconn(conn)
        coins = result[0] if result else 0
        await update.message.reply_text(f"💰 Balance: {coins} coins")
    except Exception as e:
        logger.error(f"Balance error: {e}")
        await update.message.reply_text("❌ Send /start first!")

@app.route('/')
def home():
    return "🤖 Bot is LIVE!"

@app.route('/health')
def health():
    return {"status": "ok", "db": pool is not None}

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint"""
    global application
    if application is None:
        return "Bot not ready", 503
    
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, bot)
        # Process update in background
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.process_update(update))
        loop.close()
        return "OK"
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

def init_app():
    """Initialize app and database"""
    global application, bot
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing!")
        return False
    
    # Create bot and application
    bot = Bot(BOT_TOKEN)
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    
    # Create table
    if pool:
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            coins INTEGER DEFAULT 0
        )
        """)
        conn.commit()
        cur.close()
        pool.putconn(conn)
        logger.info("✅ Database initialized")
    
    logger.info("✅ App initialized successfully")
    return True

if __name__ == '__main__':
    if init_app():
        app.run(host='0.0.0.0', port=PORT)
