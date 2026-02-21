import os
import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
from flask import Flask
import threading

app = Flask(__name__)

# Permitted role IDs for message commands
PERMITTED_ROLES = [1470596818298601567, 1470596825575854223, 1470596832794251408]

def has_permitted_role(member):
    """Check if member has any of the permitted roles"""
    if member is None:
        return False
    for role in member.roles:
        if role.id in PERMITTED_ROLES:
            return True
    return False

@app.route("/")
def home():
    return "Bot is running."

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

threading.Thread(target=run_web, daemon=True).start()
intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True         
intents.presences = True

bot = commands.Bot(command_prefix=">", intents=intents)

@bot.event
async def on_member_join(member):
    """Send a welcome message when a new member joins the server"""
    channel = bot.get_channel(1470941203343216843)
    
    if channel:
        image_embed = nextcord.Embed(
            color=0x47a88f
        )
        image_embed.set_image(
            url="https://media.discordapp.net/attachments/1474207373920043151/1474207468937805855/lcsrcwelcome.png?ex=69990232&is=6997b0b2&hm=ea3808c2593a01152f2a470cecfc4be1bdfa73d28618281146a777716c4de1d6&=&format=webp&quality=lossless&width=1356&height=678"
        )
        
        welcome_message = f"""# Welcome to Liberty County State Roleplay Community!
Thank you for joining our community, {member.mention}.

We are a ER:LC private server, focused on the community surrounding Liberty County. Departments and jobs that are offered resemble similar, but more realistic versions of the ER:LC counterparts. We host sessions daily to bi-daily, ensuring that activity spikes to encourage more fun.

> - 1. You must read our server rules listed in <#1410039042938245163>.
> - 2. You must verify with our automation services in <#1470597322499952791>. 
> - 3. In order to learn more about our community, please evaluate our <#1470597313343787030>.
> - 4. If you are ever in need of staff to answer any of your questions, you can create a **General Inquiry** ticket in <#1470597331551387702>.

Otherwise, have a fantastic day, and we hope to see you interact with our community events, channels, and features."""
        
        text_embed = nextcord.Embed(
            color=0x47a88f
        )
        text_embed.description = welcome_message
        await channel.send(embeds=[image_embed, text_embed])

@bot.event
async def on_ready():
    print(f"✅ Bot is online: {bot.user}")
    
    # Wait briefly to ensure members are cached
    await bot.wait_until_ready()
    
    # Send DM to members with specific roles
    dm_message = """If you have been DMed this message: a SHR member in Liberty County State Roleplay Community [LCSRC] has ran a new bot deployment, which means changes have been made.

# __New Bot Automation Changelog #001__

Greetings SHR and Leadership,

This is a message sent by Assistant Chairman, Pyradex letting you know that the bot has received some changes.

> The LCSRC Automation Bot now contains a new prefix [>]. Use this as a secondary prefix to slash [/] commands.
> Additionally, a new bot command has been added❗️. 
> - /message (Permits you to send messages as the bot: Embed options available for multi-line messages).
> - >message (Simple message command: deletes author's message and sends as the bot).
> - Both commands are restricted to SHR for the moment, as logistics regarding who used the commands is not available and precautions are necessary to ensure a reduction of abuse, hence the restriction.
> - `In the future:` Once logistics for this command are setup, the command will be open to Management, and potentially Supervisors, depending on trust and needs for the service.

Any questions regarding this change can be directed to my Direct Messages, or you can ping me in staff-chat. Have a great night.

Regards,
Assistant Chairman
Pyradex"""
    role_ids_to_dm = [1470596818298601567, 1470596825575854223, 1470596832794251408]
    
    # Get the guild
    guild = bot.get_guild(1470596796524535839)
    
    if guild:
        # Ensure members are fetched
        if not guild.chunked:
            await guild.chunk()
        
        # Get all members with the specified roles
        members_to_dm = []
        for member in guild.members:
            for role in member.roles:
                if role.id in role_ids_to_dm:
                    if member not in members_to_dm:  # Avoid duplicates
                        members_to_dm.append(member)
                    break
        
        print(f"📋 Found {len(members_to_dm)} members with SHR roles")
        
        # Send DM to each member
        for member in members_to_dm:
            try:
                await member.send(dm_message)
                print(f"✅ DM sent successfully to {member.name} ({member.id})")
            except Exception as e:
                print(f"❌ Failed to send DM to {member.name} ({member.id}): {e}")
        
        print(f"📬 Completed sending DMs to {len(members_to_dm)} members")

@bot.event
async def on_connect():
    print("✅ Connected to Discord!")

# >message command - plain text simple message
@bot.command(name="message")
async def message_command(ctx, *, message_text: str = None):
    """Send a plain text message via the bot"""
    # Check if user has permitted role
    if not has_permitted_role(ctx.author):
        # Delete the user's message that triggered the command
        try:
            await ctx.message.delete()
        except:
            pass
        # Send error message publicly and auto-delete after 10 seconds
        error_msg = await ctx.send(f"{ctx.author.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️.")
        await error_msg.delete(delay=10)
        return
    
    # Check if message text was provided
    if not message_text:
        await ctx.send("Please provide a message to send.", ephemeral=True)
        return
    
    # Delete the user's message that triggered the command
    try:
        await ctx.message.delete()
    except:
        pass  # If can't delete, continue anyway
    
    # Send the message to the same channel
    await ctx.send(message_text)

# /message slash command with simple and advanced options
@bot.slash_command(name="message", description="Send a message via the bot", guild_ids=[1470596796524535839])
async def slash_message(
    interaction: nextcord.Interaction,
    message_type: str = SlashOption(
        name="type",
        description="Choose simple or advanced",
        choices={"simple": "simple", "advanced": "advanced"},
        required=True
    ),
    text: str = SlashOption(
        name="text",
        description="Message text (for simple mode)",
        required=False
    ),
    embed: bool = SlashOption(
        name="embed",
        description="Use embed for advanced mode",
        required=False,
        default=False
    ),
    title: str = SlashOption(
        name="title",
        description="Title for advanced embed mode",
        required=False
    ),
    paragraph: str = SlashOption(
        name="paragraph",
        description="Multi-paragraph message for advanced mode",
        required=False
    )
):
    """Slash command to send messages with simple or advanced options"""
    # Check if user has permitted role
    if not has_permitted_role(interaction.user):
        # Send error message publicly and auto-delete after 10 seconds
        error_msg = await interaction.response.send_message(
            f"{interaction.user.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️.",
            ephemeral=False
        )
        # If the response needs to be deferred first
        if isinstance(error_msg, bool):
            # Response was deferred, need to followup
            error_msg = await interaction.followup.send(
                f"{interaction.user.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️."
            )
        await error_msg.delete(delay=10)
        return
    
    # Delete the user's message that triggered the command
    try:
        if interaction.message:
            await interaction.message.delete()
    except:
        pass  # If can't delete, continue anyway
    
    if message_type == "simple":
        # Simple mode - just send the text
        if not text:
            await interaction.response.send_message("Please provide text for simple mode.", ephemeral=True)
            return
        
        await interaction.response.send_message(text)
    
    elif message_type == "advanced":
        # Advanced mode - embed and/or multi-paragraph
        if embed:
            # Create embed
            embed_obj = nextcord.Embed(
                color=0x47a88f,
                title=title if title else None,
                description=paragraph if paragraph else None
            )
            await interaction.response.send_message(embed=embed_obj)
        else:
            # Multi-paragraph without embed
            if paragraph:
                await interaction.response.send_message(paragraph)
            else:
                await interaction.response.send_message("Please provide content for advanced mode.", ephemeral=True)

bot.run(os.getenv("TOKEN"), reconnect=True)
