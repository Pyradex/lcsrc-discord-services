import os
import nextcord
from nextcord.ext import commands
from flask import Flask
import threading

# Flask keep-alive
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

threading.Thread(target=run_web, daemon=True).start()

# Enable ALL intents (fixes the error!)
intents = nextcord.Intents.default()
intents.message_content = True    # REQUIRED - Enable in Developer Portal!
intents.members = True           # Optional - Enable in Developer Portal!
intents.presences = True         # Optional - Enable in Developer Portal!

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online: {bot.user}")

@bot.event
async def on_connect():
    print("✅ Connected to Discord!")

bot.run(os.getenv("TOKEN"), reconnect=True)
