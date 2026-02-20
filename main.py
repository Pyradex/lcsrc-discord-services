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
async def on_member_join(member):
    """Send a welcome message when a new member joins the server"""
    channel = bot.get_channel(1470941203343216843)
    
    if channel:
        # Create the image embed (Embed 1)
        image_embed = nextcord.Embed(
            color=0x47a88f  # #47a88f in hexadecimal
        )
        image_embed.set_image(
            url="https://media.discordapp.net/attachments/1474207373920043151/1474207468937805855/lcsrcwelcome.png?ex=69990232&is=6997b0b2&hm=ea3808c2593a01152f2a470cecfc4be1bdfa73d28618281146a777716c4de1d6&=&format=webp&quality=lossless&width=1356&height=678"
        )
        
        # Create the text embed (Embed 2)
        welcome_message = f"""# Welcome to Liberty County State Roleplay Community!
Thank you for joining our community, {member.mention}.

We are a ER:LC private server, focused on the community surrounding Liberty County. Departments and jobs that are offered resemble similar, but more realistic versions of the ER:LC counterparts. We host sessions daily to bi-daily, ensuring that activity spikes to encourage more fun.

> - 1. You must read our server rules listed in <#1410039042938245163>.
> - 2. You must verify with our automation services in <#1470597322499952791>. 
> - 3. In order to learn more about our community, please evaluate our <#1470597313343787030>.
> - 4. If you are ever in need of staff to answer any of your questions, you can create a **General Inquiry** ticket in <#1470597331551387702>.

Otherwise, have a fantastic day, and we hope to see you interact with our community events, channels, and features."""
        
        text_embed = nextcord.Embed(
            color=0x47a88f  # #47a88f in hexadecimal
        )
        text_embed.description = welcome_message
        
        # Send both embeds to the welcome channel
        await channel.send(embeds=[image_embed, text_embed])

@bot.event
async def on_ready():
    print(f"✅ Bot is online: {bot.user}")

@bot.event
async def on_connect():
    print("✅ Connected to Discord!")

bot.run(os.getenv("TOKEN"), reconnect=True)
