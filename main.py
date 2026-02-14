import os
import urllib.parse
import logging
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import telegram
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ENV
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))

print(f"🚀 Starting main.py - Python 3.11 - PORT: {PORT}")

# Database
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
    print("✅ DB pool ready")
else:
    print("❌ NO DATABASE_URL")

# Bot instance
bot = telegram.Bot(BOT_TOKEN) if BOT_TOKEN else None

def get_db():
    return pool.getconn()

def put_db(conn):
    pool.putconn(conn)

def create_table():
    if not pool:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        coins INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    cur.close()
    put_db(conn)
    print("✅ Table created")

def handle_start(message):
    try:
        user_id = message.from_user.id
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        conn.commit()
        cur.close()
        put_db(conn)
        bot.send_message(chat_id=message.chat.id, text="✅ Welcome! Use /balance")
    except Exception as e:
        print(f"Start error: {e}")
        bot.send_message(chat_id=message.chat.id, text="❌ Error")

def handle_balance(message):
    try:
        user_id = message.from_user.id
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT coins FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        put_db(conn)
        coins = result[0] if result else 0
        bot.send_message(chat_id=message.chat.id, text=f"💰 Balance: {coins} coins")
    except Exception as e:
        print(f"Balance error: {e}")
        bot.send_message(chat_id=message.chat.id, text="❌ Send /start first!")

@app.route('/')
def home():
    return "🤖 Bot LIVE! Python 3.11"

@app.route('/health')
def health():
    return jsonify({"status": "ok", "db": pool is not None, "python": "3.11"})

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        update = telegram.Update.de_json(data, bot)
        
        if update and update.message:
            text = update.message.text or ""
            if text == '/start':
                handle_start(update.message)
            elif text == '/balance':
                handle_balance(update.message)
        
        return "OK"
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 500

if __name__ == '__main__':
    create_table()
    print("🚀 Flask starting...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
