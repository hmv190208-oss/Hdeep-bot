import os
import psycopg2
import random
import time
import threading
from flask import Flask, render_template_string, request, redirect
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
c = conn.cursor()

# Create tables
c.execute("""
CREATE TABLE IF NOT EXISTS users(
id BIGINT PRIMARY KEY,
coins INTEGER DEFAULT 100,
last_watch BIGINT DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS posts(
id SERIAL PRIMARY KEY,
user_id BIGINT,
link TEXT
)
""")

ads = ["ðﾟﾔﾥ Promote here!", "ðﾟﾚﾀ Grow fast!", "ðﾟﾒﾰ Advertise now!"]

def get_user(uid):
    c.execute("SELECT * FROM users WHERE id=%s", (uid,))
    return c.fetchone()

def add_user(uid):
    c.execute("INSERT INTO users(id) VALUES(%s) ON CONFLICT DO NOTHING", (uid,))

# -------- TELEGRAM BOT -------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not get_user(uid):
        add_user(uid)
    await update.message.reply_text("Welcome to HDeep Views Exchange Bot ðﾟﾚﾀ")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"Coins: {user[1]}")

async def boost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["boosting"] = True
    await update.message.reply_text("Send post link")

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("boosting"):
        uid = update.effective_user.id
        link = update.message.text
        c.execute("INSERT INTO posts(user_id,link) VALUES(%s,%s)", (uid, link))
        c.execute("UPDATE users SET coins=coins-20 WHERE id=%s", (uid,))
        await update.message.reply_text("Post added ✅")
        context.user_data["boosting"] = False

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT * FROM posts ORDER BY RANDOM() LIMIT 1")
    post = c.fetchone()
    if not post:
        await update.message.reply_text("No posts available.")
        return

    ad = random.choice(ads)
    keyboard = [[InlineKeyboardButton("Watched", callback_data="watched")]]

    await update.message.reply_text(
        f"{post[2]}\n\nAd: {ad}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data["watch_time"] = time.time()

async def watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if time.time() - context.user_data.get("watch_time", 0) < 10:
        await query.edit_message_text("Wait 10 seconds ❌")
        return

    uid = query.from_user.id
    c.execute("UPDATE users SET coins=coins+5 WHERE id=%s", (uid,))
    await query.edit_message_text("+5 Coins ✅")

# -------- FLASK DASHBOARD -------- #

app = Flask(__name__)

LOGIN_PAGE = """
<form method="POST">
<input type="password" name="password" placeholder="Admin Password"/>
<button type="submit">Login</button>
</form>
"""

DASHBOARD_PAGE = """
<h2>HDeep Admin Dashboard</h2>
<h3>Total Users: {{users_count}}</h3>
<h3>Total Posts: {{posts_count}}</h3>

<h3>Users</h3>
{% for u in users %}
<p>ID: {{u[0]}} | Coins: {{u[1]}}</p>
{% endfor %}

<h3>Posts</h3>
{% for p in posts %}
... <p>User: {{p[1]}} | {{p[2]}}</p>
... {% endfor %}
... """
... 
... @app.route("/", methods=["GET", "POST"])
... def login():
...     if request.method == "POST":
...         if request.form["password"] == ADMIN_PASSWORD:
...             return redirect("/dashboard")
...     return LOGIN_PAGE
... 
... @app.route("/dashboard")
... def dashboard():
...     c.execute("SELECT * FROM users")
...     users = c.fetchall()
... 
...     c.execute("SELECT * FROM posts")
...     posts = c.fetchall()
... 
...     return render_template_string(
...         DASHBOARD_PAGE,
...         users=users,
...         posts=posts,
...         users_count=len(users),
...         posts_count=len(posts)
...     )
... 
... def run_bot():
...     application = ApplicationBuilder().token(BOT_TOKEN).build()
... 
...     application.add_handler(CommandHandler("start", start))
...     application.add_handler(CommandHandler("balance", balance))
...     application.add_handler(CommandHandler("boost", boost))
...     application.add_handler(CommandHandler("watch", watch))
...     application.add_handler(CallbackQueryHandler(watched))
...     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link))
... 
...     application.run_polling()
... 
... if __name__ == "__main__":
...     threading.Thread(target=run_bot).start()
