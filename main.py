import os
import nextcord
from nextcord.ext import commands
from flask import Flask
import threading

# ------------------------------
# RENDER WEB SERVICE FIX (REQUIRED)
# ------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Start Flask web server in background
threading.Thread(target=run_web).start()

# ------------------------------
# BOT SETUP
# ------------------------------
intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

# ------------------------------
# RUN BOT
# ------------------------------
bot.run(os.getenv("TOKEN"))
