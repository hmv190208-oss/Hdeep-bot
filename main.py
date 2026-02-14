import os
import threading
import psycopg2
from flask import Flask, request, redirect, render_template_string
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =============================
# ENV VARIABLES
# =============================

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# =============================
# DATABASE CONNECTION
# =============================

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
c = conn.cursor()

# Create tables if not exist
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    coins INT DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    link TEXT
)
""")

# =============================
# FLASK APP
# =============================

app = Flask(__name__)

LOGIN_PAGE = """
<h2>Admin Login</h2>
<form method="post">
    <input type="password" name="password" placeholder="Enter password"/>
    <button type="submit">Login</button>
</form>
"""

DASHBOARD_PAGE = """
<h2>Admin Dashboard</h2>

<h3>Total Users: {{users_count}}</h3>
<h3>Total Posts: {{posts_count}}</h3>

<h3>Users</h3>
{% for u in users %}
<p>ID: {{u[0]}} | Coins: {{u[1]}}</p>
{% endfor %}

<h3>Posts</h3>
{% for p in posts %}
<p>User: {{p[1]}} | {{p[2]}}</p>
{% endfor %}
"""

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            return redirect("/dashboard")
    return LOGIN_PAGE

@app.route("/dashboard")
def dashboard():
    c.execute("SELECT * FROM users")
    users = c.fetchall()

    c.execute("SELECT * FROM posts")
    posts = c.fetchall()

    return render_template_string(
        DASHBOARD_PAGE,
        users=users,
        posts=posts,
        users_count=len(users),
        posts_count=len(posts)
    )

# =============================
# TELEGRAM BOT FUNCTIONS
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    c.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (id, coins) VALUES (%s, %s)", (user_id, 0))

    await update.message.reply_text("Welcome! Send me a link to store.")

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text

    c.execute("INSERT INTO posts (user_id, link) VALUES (%s, %s)", (user_id, link))
    await update.message.reply_text("Link saved successfully!")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT coins FROM users WHERE id=%s", (user_id,))
    result = c.fetchone()
    coins = result[0] if result else 0
    await update.message.reply_text(f"Your balance: {coins} coins")

# =============================
# RUN BOT
# =============================

def run_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link))

    application.run_polling()

# =============================
# MAIN ENTRY
# =============================

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
