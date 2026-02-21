import os
import nextcord
from nextcord import SlashOption, ui
from nextcord.ext import commands
from flask import Flask
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# ============== CONSTANTS ==============
# Management role IDs permitted to use session commands
MANAGEMENT_ROLES = [
    1470596840369164288,
    1470596832794251408,
    1470596825575854223,
    1470596818298601567
]

# Role IDs permitted to use role command
ROLE_MANAGEMENT_ROLES = [
    1470596840369164288,
    1470596832794251408,
    1470596825575854223,
    1470596818298601567,
    1470596865601966203
]

# Role ID permitted to use dmuser command (only this one)
DMUSER_ROLE_ID = 1470596818298601567

# User ID permitted to use dmrole command (only this one)
DMROLE_USER_ID = 1261535675472281724

# Session role ID to ping
SESSION_ROLE_ID = 1470597003292573787

# Staff role ID for counting
STAFF_ROLE_ID = 1470596847423852758

# Channel IDs
SESSION_CHANNEL_ID = 1470597340992901204
PRESERVED_MESSAGE_ID = 1474612666197737584

# Guild ID
GUILD_ID = 1289789596238086194

# Cooldowns in seconds
VOTE_TO_START_COOLDOWN = 5 * 60  # 5 minutes
SHUTDOWN_COOLDOWN = 60 * 60  # 1 hour
SESSION_LOW_COOLDOWN = 10 * 60  # 10 minutes

# Auto-shutdown timers
AUTO_SHUTDOWN_INITIAL = 2 * 60 * 60  # 2 hours
AUTO_SHUTDOWN_GRACE_PERIOD = 60 * 60  # 1 hour

# Inappropriate words filter list
INAPPROPRIATE_WORDS = [
    "nigger", "nigga", "faggot", "faggot", "fag", "retard", "retarded",
    "cunt", "c0unt", "bitch", "b1tch", "bitch", "whore", "slut",
    "fucker", "fuck", "fuk", "shit", "shit", "bullshit", "bs",
    "damn", "dammit", "hell", "ass", "asshole", "a$$", "a**",
    "bastard", "dick", "cock", "pussy", "cunt", "sex",
    "rape", "rapist", "molest", "pedophile", "pedo", "nazi",
    "terrorist", "kill", "murder", "die", "suicide"
]

def contains_inappropriate_words(text: str) -> bool:
    """Check if text contains inappropriate words"""
    text_lower = text.lower()
    # Remove common leetspeak substitutions for filtering
    text_filtered = text_lower.replace("1", "i").replace("0", "o").replace("3", "e").replace("4", "a").replace("5", "s").replace("@", "a").replace("$", "s")
    
    for word in INAPPROPRIATE_WORDS:
        if word in text_filtered:
            return True
    return False

# ============== GLOBAL STATE ==============
class SessionState:
    def __init__(self):
        self.is_active = False
        self.session_start_time = None
        self.last_vote_time = None
        self.last_shutdown_time = None
        self.last_session_low_time = None
        self.session_voters = []
        self.session_initiator_id = None
        self.vote_count_needed = 0
        self.vote_message_id = None
        self.session_message_id = None
        self.session_history = []
        self.auto_shutdown_task = None
        self.pending_confirmation = False

session_state = SessionState()

# Dictionary to track session panel message IDs to their initiators
session_panel_messages = {}  # message_id -> initiator_id

def has_management_role(member):
    """Check if member has any of the permitted management roles"""
    if member is None:
        return False
    for role in member.roles:
        if role.id in MANAGEMENT_ROLES:
            return True
    return False

def has_dmuser_role(member):
    """Check if member has the dmuser role"""
    if member is None:
        return False
    for role in member.roles:
        if role.id == DMUSER_ROLE_ID:
            return True
    return False

def has_role_management_role(member):
    """Check if member has any of the permitted role management roles"""
    if member is None:
        return False
    for role in member.roles:
        if role.id in ROLE_MANAGEMENT_ROLES:
            return True
    return False

def can_modify_role(member, target_member, guild):
    """Check if member can modify target_member's role based on hierarchy"""
    if member is None or target_member is None or guild is None:
        return False
    
    # Get member's highest role
    member_highest_role = None
    for role in member.roles:
        if member_highest_role is None or role.position > member_highest_role.position:
            member_highest_role = role
    
    # Get target's highest role
    target_highest_role = None
    for role in target_member.roles:
        if target_highest_role is None or role.position > target_highest_role.position:
            target_highest_role = role
    
    # If target has no roles, member can always modify
    if target_highest_role is None:
        return True
    
    # Member needs to have a higher role than target
    if member_highest_role is None:
        return False
    
    return member_highest_role.position > target_highest_role.position

def can_start_vote():
    """Check if a vote can be started based on cooldown"""
    if session_state.last_shutdown_time:
        if time.time() - session_state.last_shutdown_time < SHUTDOWN_COOLDOWN:
            return False
    if session_state.is_active:
        return False
    return True

def can_start_session(initiator_id):
    """Check if session can be started"""
    if session_state.is_active:
        return False
    if session_state.last_vote_time:
        if time.time() - session_state.last_vote_time < VOTE_TO_START_COOLDOWN:
            if session_state.session_initiator_id != initiator_id:
                return False
    if session_state.last_shutdown_time:
        if time.time() - session_state.last_shutdown_time < SHUTDOWN_COOLDOWN:
            return False
    return True

def can_run_session_low():
    """Check if session low can be run"""
    if not session_state.is_active:
        return False
    if session_state.last_session_low_time:
        if time.time() - session_state.last_session_low_time < SESSION_LOW_COOLDOWN:
            return False
    return True

def add_to_history(action, user):
    """Add action to session history"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_name = user.display_name if user else "Unknown"
    session_state.session_history.append({
        "action": action,
        "user": display_name,
        "timestamp": timestamp
    })

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

# ============== SESSION VIEW (BUTTONS) ==============
class SessionView(ui.View):
    def __init__(self, initiator_id: int = None):
        super().__init__(timeout=None)
        self.initiator_id = initiator_id
        
        # Session Vote button
        self.vote_btn = ui.Button(
            label="Session Voting",
            style=nextcord.ButtonStyle.primary,
            custom_id="session_vote"
        )
        self.vote_btn.callback = self.vote_callback
        self.add_item(self.vote_btn)
        
        # Session Start button
        self.start_btn = ui.Button(
            label="Session Startup",
            style=nextcord.ButtonStyle.primary,
            custom_id="session_start"
        )
        self.start_btn.callback = self.start_callback
        self.add_item(self.start_btn)
        
        # Session Shutdown button
        self.shutdown_btn = ui.Button(
            label="Session Shutdown",
            style=nextcord.ButtonStyle.primary,
            custom_id="session_shutdown"
        )
        self.shutdown_btn.callback = self.shutdown_callback
        self.add_item(self.shutdown_btn)
        
        # Session Low button
        self.low_btn = ui.Button(
            label="Session Low",
            style=nextcord.ButtonStyle.primary,
            custom_id="session_low"
        )
        self.low_btn.callback = self.low_callback
        self.add_item(self.low_btn)
        
        # Session Full button
        self.full_btn = ui.Button(
            label="Session Full",
            style=nextcord.ButtonStyle.primary,
            custom_id="session_full"
        )
        self.full_btn.callback = self.full_callback
        self.add_item(self.full_btn)
        
        # Session History button
        self.history_btn = ui.Button(
            label="Sessions History",
            style=nextcord.ButtonStyle.secondary,
            custom_id="session_history"
        )
        self.history_btn.callback = self.history_callback
        self.add_item(self.history_btn)
    
    async def check_initiator(self, interaction: nextcord.Interaction) -> bool:
        """Check if the interaction is from the original initiator"""
        if self.initiator_id is None:
            return True  # No restriction if no initiator set
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message(
                f"{interaction.user.mention}: Only the person who opened this panel can use it!",
                ephemeral=True
            )
            return False
        return True
    
    async def vote_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_start_vote():
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        modal = SessionVoteModal()
        await interaction.response.send_modal(modal)
    
    async def start_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_start_session(interaction.user.id):
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        # Start the session
        session_state.is_active = True
        session_state.session_start_time = time.time()
        session_state.last_session_low_time = None
        session_state.session_initiator_id = interaction.user.id
        session_state.last_vote_time = time.time()
        
        # Get staff count
        guild = bot.get_guild(GUILD_ID)
        staff_count = 0
        if guild:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                staff_count = len(staff_role.members)
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Ping outside embed first
            await session_channel.send(f"<@&{SESSION_ROLE_ID}>")
            
            # Send session start embed
            embed = nextcord.Embed(
                color=0x47a88f,
                title="__Session Has Started__"
            )
            embed.description = f"""> After enough votes, or direct action by a Management member, a session has begun. Please refer to below for statistics.

> - ER:LC In-Game: N/A  
> - Staff Online: {staff_count}
> - ER:LC Code: LCsRp
"""
            await session_channel.send(embed=embed)
            
            # Send session voters list
            if session_state.session_voters:
                voters_mentions = " ".join(session_state.session_voters)
                await session_channel.send(f"Session Voters: {voters_mentions}")
        
        add_to_history("Session Started", interaction.user)
        
        await interaction.response.send_message("Session has been started!", ephemeral=True)
    
    async def shutdown_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        session_state.is_active = False
        session_state.session_start_time = None
        session_state.session_voters = []
        session_state.session_initiator_id = None
        session_state.vote_count_needed = 0
        session_state.vote_message_id = None
        session_state.pending_confirmation = False
        session_state.last_shutdown_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Send shutdown message
            await session_channel.send("__Session Shutdown__\n\nA session has been shutdown in Liberty County State Roleplay Community [LCSRC]. Thanks for joining us on a good session. See you soon!")
        
        add_to_history("Session Shutdown", interaction.user)
        
        await interaction.response.send_message("Session has been shutdown!", ephemeral=True)
    
    async def low_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_run_session_low():
            await interaction.response.send_message("Session Low is on cooldown. Please wait before using it again.", ephemeral=True)
            return
        
        session_state.last_session_low_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            await session_channel.send(f"<@&{SESSION_ROLE_ID}> Session is currently low on members. Please invite more players!")
        
        add_to_history("Session Low", interaction.user)
        
        await interaction.response.send_message("Session Low message sent!", ephemeral=True)
    
    async def full_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            await session_channel.send("Session is now full!")
        
        add_to_history("Session Full", interaction.user)
        
        await interaction.response.send_message("Session Full message sent!", ephemeral=True)
    
    async def history_callback(self, interaction: nextcord.Interaction):
        # Check if user is the initiator
        if not await self.check_initiator(interaction):
            return
        
        # Check if user has management role
        if not has_management_role(interaction.user):
            await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
            return
        
        if not session_state.session_history:
            embed = nextcord.Embed(
                title="Session History",
                description="No session history available.",
                color=0x47a88f
            )
        else:
            history_text = ""
            for entry in session_state.session_history:
                history_text += f"**{entry['user']}** - {entry['action']} - <t:{int(time.mktime(datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S').timetuple()))}:f>\n"
            
            embed = nextcord.Embed(
                title="Session History",
                description=history_text,
                color=0x47a88f
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============== VOTE CONFIRMATION VIEW ==============
class VoteConfirmView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        
    @ui.button(label="Confirm Session Start", style=nextcord.ButtonStyle.green, custom_id="confirm_session_start")
    async def confirm_start(self, button: ui.Button, interaction: nextcord.Interaction):
        if not session_state.is_active:
            # Start the session
            session_state.is_active = True
            session_state.session_start_time = time.time()
            session_state.last_session_low_time = None
            session_state.pending_confirmation = False
            
            # Get staff count
            guild = bot.get_guild(GUILD_ID)
            staff_count = 0
            if guild:
                staff_role = guild.get_role(STAFF_ROLE_ID)
                if staff_role:
                    staff_count = len(staff_role.members)
            
            # Get session channel
            session_channel = bot.get_channel(SESSION_CHANNEL_ID)
            
            if session_channel:
                # Delete messages except preserved one
                try:
                    async for message in session_channel.history(limit=100):
                        if message.id != PRESERVED_MESSAGE_ID:
                            try:
                                await message.delete()
                            except:
                                pass
                except:
                    pass
                
                # Ping outside embed
                await session_channel.send(f"<@&{SESSION_ROLE_ID}>")
                
                # Send session start embed
                embed = nextcord.Embed(
                    color=0x47a88f,
                    title="__Session Has Started__"
                )
                embed.description = f"""> After enough votes, or direct action by a Management member, a session has begun. Please refer to below for statistics.

> - ER:LC In-Game: N/A  
> - Staff Online: {staff_count}
> - ER:LC Code: LCsRp
"""
                await session_channel.send(embed=embed)
                
                # Send session voters list
                if session_state.session_voters:
                    voters_mentions = " ".join(session_state.session_voters)
                    await session_channel.send(f"Session Voters: {voters_mentions}")
            
            add_to_history("Session Started", interaction.user)
            
            await interaction.response.send_message("Session has been started!", ephemeral=True)
        else:
            await interaction.response.send_message("A session has already started!", ephemeral=True)
        
        self.stop()
    
    @ui.button(label="Cancel", style=nextcord.ButtonStyle.red, custom_id="cancel_session_start")
    async def cancel_start(self, button: ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message("Session start cancelled.", ephemeral=True)
        self.stop()

# ============== AUTO SHUTDOWN CONFIRMATION VIEW ==============
class AutoShutdownView(ui.View):
    def __init__(self):
        super().__init__(timeout=3600)
        
    @ui.button(label="Yes - Continue Session", style=nextcord.ButtonStyle.green, custom_id="auto_continue_session")
    async def continue_session(self, button: ui.Button, interaction: nextcord.Interaction):
        session_state.pending_confirmation = False
        await interaction.response.send_message("Session will continue. Timer reset.", ephemeral=True)
        self.stop()
    
    @ui.button(label="No - Shutdown Session", style=nextcord.ButtonStyle.red, custom_id="auto_shutdown_session")
    async def shutdown_session(self, button: ui.Button, interaction: nextcord.Interaction):
        await self.shutdown(interaction)
        self.stop()
    
    async def shutdown(self, interaction: nextcord.Interaction):
        session_state.is_active = False
        session_state.session_start_time = None
        session_state.session_voters = []
        session_state.session_initiator_id = None
        session_state.vote_count_needed = 0
        session_state.vote_message_id = None
        session_state.pending_confirmation = False
        session_state.last_shutdown_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Send shutdown message
            await session_channel.send("__Session Shutdown__\n\nA session has been shutdown in Liberty County State Roleplay Community [LCSRC]. Thanks for joining us on a good session. See you soon!")
        
        add_to_history("Session Shutdown (Auto)", interaction.user)
        
        await interaction.response.send_message("Session has been shutdown!", ephemeral=True)

# ============== SESSION VOTE MODAL ==============
class SessionVoteModal(ui.Modal):
    def __init__(self):
        super().__init__("Session Vote Count")
        
        self.vote_count = ui.TextInput(
            label="Number of votes needed to start session",
            placeholder="Enter vote count (e.g., 5)",
            required=True,
            min_length=1,
            max_length=3
        )
        self.add_item(self.vote_count)
    
    async def callback(self, interaction: nextcord.Interaction):
        try:
            vote_count = int(self.vote_count.value)
        except:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)
            return
        
        if not can_start_vote():
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        session_state.vote_count_needed = vote_count
        session_state.session_voters = []
        session_state.session_initiator_id = interaction.user.id
        session_state.last_vote_time = time.time()
        
        # Get staff count
        guild = bot.get_guild(GUILD_ID)
        staff_count = 0
        if guild:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                staff_count = len(staff_role.members)
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Ping outside embed first
            await session_channel.send(f"<@&{SESSION_ROLE_ID}>")
            
            # Send vote embed
            embed = nextcord.Embed(
                color=0x47a88f,
                title="__Session Voting__ [LCSRC]"
            )
            embed.description = f"""> A vote for a session has occured by Liberty County State Roleplay Community Management. In order for a vote to occur, please react below with the <:Checkmark:1474615531431657572>. Once {vote_count} has been reached, a session will plan to start.
"""
            vote_msg = await session_channel.send(embed=embed)
            session_state.vote_message_id = vote_msg.id
            
            # Add checkmark reaction
            await vote_msg.add_reaction("<:Checkmark:1474615531431657572>")
        
        add_to_history(f"Session Vote Started (Need {vote_count} votes)", interaction.user)
        
        # Send DM to initiator with confirmation buttons
        try:
            view = VoteConfirmView()
            await interaction.user.send("A session vote has been initiated. Click below to start the session when ready:", view=view)
        except:
            pass
        
        await interaction.response.send_message("Session vote has been initiated!", ephemeral=True)

# ============== BUTTON HANDLERS ==============
@bot.listen("on_interaction")
async def on_interaction(interaction: nextcord.Interaction):
    if not isinstance(interaction, nextcord.Interaction):
        return
    
    if interaction.type != nextcord.InteractionType.component:
        return
    
    custom_id = interaction.data.custom_id
    
    # Get the message ID from the interaction
    message_id = interaction.message.id if interaction.message else None
    
    # Check if this is a session panel and verify initiator
    if message_id and message_id in session_panel_messages:
        initiator_id = session_panel_messages[message_id]
        if interaction.user.id != initiator_id:
            await interaction.response.send_message(
                f"{interaction.user.mention}: Only the person who opened this panel can use it!",
                ephemeral=True
            )
            return
    
    # Check if user has management role
    if not has_management_role(interaction.user):
        await interaction.response.send_message(f"{interaction.user.mention}: You don't have permission to use this!", ephemeral=True)
        return
    
    # Session Vote button
    if custom_id == "session_vote":
        if session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_start_vote():
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        modal = SessionVoteModal()
        await interaction.response.send_modal(modal)
        return
    
    # Session Start button
    if custom_id == "session_start":
        if session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_start_session(interaction.user.id):
            await interaction.response.send_message(f"<@{interaction.user.id}> has already started a session, hence that action cannot occur.", ephemeral=False)
            return
        
        # Start the session
        session_state.is_active = True
        session_state.session_start_time = time.time()
        session_state.last_session_low_time = None
        session_state.session_initiator_id = interaction.user.id
        session_state.last_vote_time = time.time()
        
        # Get staff count
        guild = bot.get_guild(GUILD_ID)
        staff_count = 0
        if guild:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                staff_count = len(staff_role.members)
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Ping outside embed first
            await session_channel.send(f"<@&{SESSION_ROLE_ID}>")
            
            # Send session start embed
            embed = nextcord.Embed(
                color=0x47a88f,
                title="__Session Has Started__"
            )
            embed.description = f"""> After enough votes, or direct action by a Management member, a session has begun. Please refer to below for statistics.

> - ER:LC In-Game: N/A  
> - Staff Online: {staff_count}
> - ER:LC Code: LCsRp
"""
            await session_channel.send(embed=embed)
            
            # Send session voters list
            if session_state.session_voters:
                voters_mentions = " ".join(session_state.session_voters)
                await session_channel.send(f"Session Voters: {voters_mentions}")
        
        add_to_history("Session Started", interaction.user)
        
        await interaction.response.send_message("Session has been started!", ephemeral=True)
        return
    
    # Session Shutdown button
    if custom_id == "session_shutdown":
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        session_state.is_active = False
        session_state.session_start_time = None
        session_state.session_voters = []
        session_state.session_initiator_id = None
        session_state.vote_count_needed = 0
        session_state.vote_message_id = None
        session_state.pending_confirmation = False
        session_state.last_shutdown_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            # Delete messages except preserved one
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            # Send shutdown message
            await session_channel.send("__Session Shutdown__\n\nA session has been shutdown in Liberty County State Roleplay Community [LCSRC]. Thanks for joining us on a good session. See you soon!")
        
        add_to_history("Session Shutdown", interaction.user)
        
        await interaction.response.send_message("Session has been shutdown!", ephemeral=True)
        return
    
    # Session Low button
    if custom_id == "session_low":
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        if not can_run_session_low():
            await interaction.response.send_message("Session Low is on cooldown. Please wait before using it again.", ephemeral=True)
            return
        
        session_state.last_session_low_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            await session_channel.send(f"<@&{SESSION_ROLE_ID}> Session is currently low on members. Please invite more players!")
        
        add_to_history("Session Low", interaction.user)
        
        await interaction.response.send_message("Session Low message sent!", ephemeral=True)
        return
    
    # Session Full button
    if custom_id == "session_full":
        if not session_state.is_active:
            await interaction.response.send_message(f"<@{interaction.user.id}> has already ended a session, hence that action cannot occur.", ephemeral=False)
            return
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            await session_channel.send("Session is now full!")
        
        add_to_history("Session Full", interaction.user)
        
        await interaction.response.send_message("Session Full message sent!", ephemeral=True)
        return
    
    # Sessions History button
    if custom_id == "session_history":
        if not session_state.session_history:
            embed = nextcord.Embed(
                title="Session History",
                description="No session history available.",
                color=0x47a88f
            )
        else:
            history_text = ""
            for entry in session_state.session_history:
                history_text += f"**{entry['user']}** - {entry['action']} - <t:{int(time.mktime(datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S').timetuple()))}:f>\n"
            
            embed = nextcord.Embed(
                title="Session History",
                description=history_text,
                color=0x47a88f
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Auto-shutdown confirmation buttons
    if custom_id == "auto_continue_session":
        session_state.pending_confirmation = False
        await interaction.response.send_message("Session will continue. Timer reset.", ephemeral=True)
        return
    
    if custom_id == "auto_shutdown_session":
        session_state.is_active = False
        session_state.session_start_time = None
        session_state.session_voters = []
        session_state.session_initiator_id = None
        session_state.pending_confirmation = False
        session_state.last_shutdown_time = time.time()
        
        session_channel = bot.get_channel(SESSION_CHANNEL_ID)
        
        if session_channel:
            try:
                async for message in session_channel.history(limit=100):
                    if message.id != PRESERVED_MESSAGE_ID:
                        try:
                            await message.delete()
                        except:
                            pass
            except:
                pass
            
            await session_channel.send("__Session Shutdown__\n\nA session has been shutdown in Liberty County State Roleplay Community [LCSRC]. Thanks for joining us on a good session. See you soon!")
        
        add_to_history("Session Shutdown (Auto)", interaction.user)
        
        await interaction.response.send_message("Session has been auto-shutdown!", ephemeral=True)
        return

# ============== AUTO SHUTDOWN TASK ==============
async def check_auto_shutdown():
    """Check if session needs auto-shutdown"""
    while True:
        await bot.wait_until_ready()
        
        if session_state.is_active and session_state.session_start_time and not session_state.pending_confirmation:
            elapsed = time.time() - session_state.session_start_time
            
            # After 2 hours, ask for confirmation
            if elapsed >= AUTO_SHUTDOWN_INITIAL:
                session_state.pending_confirmation = True
                
                # Find the session initiator
                if session_state.session_initiator_id:
                    guild = bot.get_guild(GUILD_ID)
                    if guild:
                        member = guild.get_member(session_state.session_initiator_id)
                        if member:
                            try:
                                view = AutoShutdownView()
                                await member.send("The session has been running for 2 hours. Do you want to continue?", view=view)
                            except:
                                # If can't DM, just shutdown
                                session_state.is_active = False
                                session_state.session_start_time = None
                                session_state.last_shutdown_time = time.time()
                                
                                session_channel = bot.get_channel(SESSION_CHANNEL_ID)
                                if session_channel:
                                    try:
                                        async for message in session_channel.history(limit=100):
                                            if message.id != PRESERVED_MESSAGE_ID:
                                                try:
                                                    await message.delete()
                                                except:
                                                    pass
                                    except:
                                        pass
                                    await session_channel.send("__Session Shutdown__\n\nA session has been auto-shutdown after 2 hours of inactivity.")
                
                # After 1 more hour (total 3 hours), auto shutdown if not confirmed
                await bot.wait_until_ready()
                await asyncio.sleep(AUTO_SHUTDOWN_GRACE_PERIOD)
                
                if session_state.pending_confirmation:
                    session_state.is_active = False
                    session_state.session_start_time = None
                    session_state.last_shutdown_time = time.time()
                    session_state.pending_confirmation = False
                    
                    session_channel = bot.get_channel(SESSION_CHANNEL_ID)
                    if session_channel:
                        try:
                            async for message in session_channel.history(limit=100):
                                if message.id != PRESERVED_MESSAGE_ID:
                                    try:
                                        await message.delete()
                                    except:
                                        pass
                        except:
                            pass
                        await session_channel.send("__Session Shutdown__\n\nA session has been auto-shutdown after 3 hours of inactivity.")
        
        await asyncio.sleep(60)  # Check every minute

# Need to import asyncio for the auto-shutdown task
import asyncio

# ============== EVENTS ==============
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
    
    # Sync slash commands to the guild
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            # Sync application commands to the guild
            await bot.sync_application_commands(guild=guild)
            print(f"✅ Slash commands synced to guild: {guild.name}")
        else:
            print(f"❌ Guild not found for command registration!")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")
    
    # Register session view persistently
    bot.add_view(SessionView(initiator_id=None))
    
    # Start auto-shutdown task
    asyncio.create_task(check_auto_shutdown())
    
    print(f"🤖 Bot ready for use!")

@bot.event
async def on_connect():
    print("✅ Connected to Discord!")

# ============== COMMANDS ==============

# >sessions command - message command that shows session panel as a reply
@bot.command(name="sessions")
async def sessions_command(ctx):
    """Show session management panel (for management only)"""
    # Check if user has permitted role
    if not has_management_role(ctx.author):
        error_msg = await ctx.reply(f"{ctx.author.mention}: As you are not Management, you are not permitted to use this command ⚠️.")
        await error_msg.delete(delay=10)
        return
    
    # Create session management embed
    embed = nextcord.Embed(
        color=0x47a88f,
        title="__Session Management__"
    )
    embed.description = """> Since you are Management, you have the ability to manage sessions within Liberty County State Roleplay Community [LCSRC].

> - Session Vote [Permits you to chose a number of votes in order to start a session]
> - Session Start [Starts the session.]
> - Session Low [Notifies the server that the member count needs to be raised, as it is low.]
> - Session Shutdown [Notifies the server that the server is shutdown].
> - Session Full [Notifies the server that the session is full]
"""
    
    view = SessionView(initiator_id=ctx.author.id)
    # Send the panel to the user
    await ctx.send(embed=embed, view=view)

# /sessions slash command
@bot.slash_command(name="sessions", description="Manage session panel", guild_ids=[GUILD_ID])
async def slash_sessions(interaction: nextcord.Interaction):
    """Show session management panel (for management only)"""
    # Check if user has permitted role
    if not has_management_role(interaction.user):
        await interaction.response.send_message(
            f"{interaction.user.mention}: As you are not Management, you are not permitted to use this command ⚠️.",
            ephemeral=True
        )
        return
    
    # Create session management embed
    embed = nextcord.Embed(
        color=0x47a88f,
        title="__Session Management__"
    )
    embed.description = """> Since you are Management, you have the ability to manage sessions within Liberty County State Roleplay Community [LCSRC].

> - Session Vote [Permits you to chose a number of votes in order to start a session]
> - Session Start [Starts the session.]
> - Session Low [Notifies the server that the member count needs to be raised, as it is low.]
> - Session Shutdown [Notifies the server that the server is shutdown].
> - Session Full [Notifies the server that the session is full]
"""
    
    view = SessionView(initiator_id=interaction.user.id)
    # Send the panel and get the response
    await interaction.response.send_message(embed=embed, view=view)

# /say slash command (replaces /message)
@bot.slash_command(name="say", description="Send a message via the bot", guild_ids=[GUILD_ID])
async def slash_say(
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
    """Slash command to send messages (replaces /message)"""
    # Check if user has permitted role
    if not has_management_role(interaction.user):
        await interaction.response.send_message(
            f"{interaction.user.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️.",
            ephemeral=True
        )
        return
    
    if message_type == "simple":
        if not text:
            await interaction.response.send_message("Please provide text for simple mode.", ephemeral=True)
            return
        
        # Check for inappropriate words
        if contains_inappropriate_words(text):
            await interaction.response.send_message(
                "⚠️ Your message contains inappropriate content and cannot be sent.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(text)
    
    elif message_type == "advanced":
        if embed:
            # Check for inappropriate words in both title and paragraph
            check_text = f"{title or ''} {paragraph or ''}"
            if contains_inappropriate_words(check_text):
                await interaction.response.send_message(
                    "⚠️ Your message contains inappropriate content and cannot be sent.",
                    ephemeral=True
                )
                return
            
            embed_obj = nextcord.Embed(
                color=0x47a88f,
                title=title if title else None,
                description=paragraph if paragraph else None
            )
            await interaction.response.send_message(embed=embed_obj)
        else:
            if paragraph:
                # Check for inappropriate words
                if contains_inappropriate_words(paragraph):
                    await interaction.response.send_message(
                        "⚠️ Your message contains inappropriate content and cannot be sent.",
                        ephemeral=True
                    )
                    return
                await interaction.response.send_message(paragraph)
            else:
                await interaction.response.send_message("Please provide content for advanced mode.", ephemeral=True)

# /role slash command - Add or remove a role from a user
@bot.slash_command(name="role", description="Add or remove a role from a user", guild_ids=[GUILD_ID])
async def slash_role(
    interaction: nextcord.Interaction,
    user: nextcord.Member = SlashOption(
        name="user",
        description="User to add/remove role from",
        required=True
    ),
    role: nextcord.Role = SlashOption(
        name="role",
        description="Role to add or remove",
        required=True
    )
):
    """Slash command to add or remove a role from a user"""
    # Check if user has permitted role
    if not has_management_role(interaction.user):
        await interaction.response.send_message(
            f"{interaction.user.mention}: As you are not Management, you are not permitted to use this command ⚠️.",
            ephemeral=True
        )
        return
    
    # Check if user has the role
    if role in user.roles:
        # Remove the role
        await user.remove_roles(role)
        action = "removed"
        response = f"-role {role.name} removed."
        
        # Send DM to user about role removal
        try:
            dm_embed = nextcord.Embed(
                color=0xff6b6b,
                title="Role Removed"
            )
            dm_embed.description = f"**Role:** {role.name}\n\n**Action taken by:** {interaction.user.display_name}"
            await user.send(embed=dm_embed)
        except:
            pass  # If DM fails, continue anyway
    else:
        # Add the role
        await user.add_roles(role)
        action = "added"
        response = f"+role {role.name} added."
        
        # Send DM to user about role addition
        try:
            dm_embed = nextcord.Embed(
                color=0x47a88f,
                title="Role Added"
            )
            dm_embed.description = f"**Role:** {role.name}\n\n**Action taken by:** {interaction.user.display_name}"
            await user.send(embed=dm_embed)
        except:
            pass  # If DM fails, continue anyway
    
    await interaction.response.send_message(response, ephemeral=True)

# /message slash command - Send a message via the bot
@bot.slash_command(name="message", description="Send a message via the bot", guild_ids=[GUILD_ID])
async def slash_message(
    interaction: nextcord.Interaction,
    text: str = SlashOption(
        name="text",
        description="Message text to send",
        required=True
    )
):
    """Slash command to send a plain text message"""
    # Check if user has permitted role
    if not has_management_role(interaction.user):
        await interaction.response.send_message(
            f"{interaction.user.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️.",
            ephemeral=True
        )
        return
    
    # Check for inappropriate words
    if contains_inappropriate_words(text):
        await interaction.response.send_message(
            "⚠️ Your message contains inappropriate content and cannot be sent.",
            ephemeral=True
        )
        return
    
    await interaction.response.send_message(text)

# >message command - plain text simple message (kept for backwards compatibility)
@bot.command(name="message")
async def message_command(ctx, *, message_text: str = None):
    """Send a plain text message via the bot"""
    # Check if user has permitted role
    if not has_management_role(ctx.author):
        try:
            await ctx.message.delete()
        except:
            pass
        error_msg = await ctx.send(f"{ctx.author.mention}: As you are not a Senior High Rank, you are not permitted to use this command ⚠️.")
        await error_msg.delete(delay=10)
        return
    
    if not message_text:
        await ctx.send("Please provide a message to send.", ephemeral=True)
        return
    
    # Check for inappropriate words
    if contains_inappropriate_words(message_text):
        error_msg = await ctx.send("⚠️ Your message contains inappropriate content and cannot be sent.")
        await error_msg.delete(delay=10)
        return
    
    try:
        await ctx.message.delete()
    except:
        pass
    
    await ctx.send(message_text)

# ># >dmuser command - Send a DM to a user (only for specific role)
@bot.command(name="dmuser")
async def dmuser_command(ctx, user: nextcord.Member, *, message: str):
    """DM a user with a message (requires specific role)"""
    # Check if user has dmuser role
    if not has_dmuser_role(ctx.author):
        try:
            await ctx.message.delete()
        except:
            pass
        error_msg = await ctx.send(f"{ctx.author.mention}: As you are not Management, you are not permitted to use this command ⚠️.")
        await error_msg.delete(delay=10)
        return
    
    # Check for inappropriate words
    if contains_inappropriate_words(message):
        error_msg = await ctx.send("⚠️ Your message contains inappropriate content and cannot be sent.")
        await error_msg.delete(delay=10)
        return

    if not args:
        await ctx.send("Usage: `>role @user @role` or `>role @user role name`", ephemeral=True)
        return

    # Delete the user's command message
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Send DM to the target user
    try:
        dm_embed = nextcord.Embed(
            color=0x47a88f,
            title="Message from LCSRC Management"
        )
        dm_embed.description = f"**Message:** {message}\n\n**Sent by:** {ctx.author.display_name}"
        await user.send(embed=dm_embed)
        
        # Confirm to the command user
        confirm_msg = await ctx.send(f"✅ DM sent to {user.display_name}!")
        await confirm_msg.delete(delay=5)
    except:
        error_msg = await ctx.send(f"❌ Could not send DM to {user.display_name}. They may have DMs disabled.")
        await error_msg.delete(delay=10)

# >role command - Add or remove a role from a user
@bot.command(name="role")
async def role_command(ctx, *, args: str = None):
    """Add or remove a role from a user (for management only)
    
    Usage: >role @user @role OR >role @user role name (partial match)
    Example: >role @User manag OR >role @User @LCSRC | Management Team
    """
    # Check if user has permitted role
    if not has_management_role(ctx.author):
        try:
            await ctx.message.delete()
        except:
            pass
        error_msg = await ctx.send(f"{ctx.author.mention}: As you are not Management, you are not permitted to use this command ⚠️.")
        await error_msg.delete(delay=10)
        return
    
    # Delete the user's command message
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Check if user has the role
    if role in user.roles:
        # Remove the role
        await user.remove_roles(role)
        action = "removed"
        response = f"-role {role.name} removed."
        
        # Send DM to user about role removal
        try:
            dm_embed = nextcord.Embed(
                color=0xff6b6b,
                title="Role Removed"
            )
            dm_embed.description = f"**Role:** {role.name}\n\n**Action taken by:** {ctx.author.display_name}"
            await user.send(embed=dm_embed)
        except:
            pass  # If DM fails, continue anyway
    else:
        # Add the role
        await user.add_roles(role)
        action = "added"
        response = f"+role {role.name} added."
        
        # Send DM to user about role addition
        try:
            dm_embed = nextcord.Embed(
                color=0x47a88f,
                title="Role Added"
            )
            dm_embed.description = f"**Role:** {role.name}\n\n**Action taken by:** {ctx.author.display_name}"
            await user.send(embed=dm_embed)
        except:
            pass  # If DM fails, continue anyway
    
    # Confirm the action
    confirm_msg = await ctx.send(response)
    await confirm_msg.delete(delay=10)

# >dmrole command - DM users with specific role IDs
@bot.command(name="dmrole")
async def dmrole_command(ctx, *args):
    """DM users with specific role IDs
    
    Usage: >dmrole roleid1 roleid2 roleid3 ... message
    Example: >dmrole 5309285209385 2350982305982359 Hello everyone!
    
    The last argument is treated as the message, all previous args are role IDs.
    Only user ID 1261535675472281724 can use this command.
    """
    # Check if user is the permitted user
    if ctx.author.id != DMROLE_USER_ID:
        try:
            await ctx.message.delete()
        except:
            pass
        error_msg = await ctx.send(f"{ctx.author.mention}: You are prohibited from usage of this command.")
        await error_msg.delete(delay=10)
        return
    
    if not args:
        await ctx.send("Usage: `>dmrole roleid1 roleid2 ... message`", ephemeral=True)
        return
    
    # Parse arguments: all but the last are role IDs, last is the message
    args_list = list(args)
    
    if len(args_list) < 2:
        await ctx.send("Usage: `>dmrole roleid1 roleid2 ... message` (need at least 1 role ID and a message)", ephemeral=True)
        return
    
    # Extract role IDs (all args except the last)
    role_ids = []
    for arg in args_list[:-1]:
        try:
            role_id = int(arg)
            role_ids.append(role_id)
        except ValueError:
            await ctx.send(f"Invalid role ID: {arg}", ephemeral=True)
            return
    
    # The last argument is the message (join all remaining args as message)
    message = " ".join(args_list[len(role_ids):])
    
    # Check for inappropriate words
    if contains_inappropriate_words(message):
        error_msg = await ctx.send("⚠️ Your message contains inappropriate content and cannot be sent.")
        await error_msg.delete(delay=10)
        return
    
    # Delete the user's command message
    try:
        await ctx.message.delete()
    except:
        pass
    
    # Get guild and find members with the specified roles
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await ctx.send("⚠️ Could not find guild.", ephemeral=True)
        return
    
    # Get members who have ANY of the specified roles
    # We iterate through the roles to get members instead of guild.members
    # which may not be fully cached
    target_members = []
    for role_id in role_ids:
        role = guild.get_role(role_id)
        if role:
            for member in role.members:
                if member not in target_members:
                    target_members.append(member)
    
    if not target_members:
        await ctx.send("⚠️ No members found with the specified role(s).", ephemeral=True)
        return
    
    # Send DMs to all target members
    success_count = 0
    failed_count = 0
    
    dm_embed = nextcord.Embed(
        color=0x47a88f,
        title="Message from LCSRC Management"
    )
    dm_embed.description = f"**Message:** {message}\n\n**Sent by:** {ctx.author.display_name}"
    
    for member in target_members:
        try:
            await member.send(embed=dm_embed)
            success_count += 1
        except:
            failed_count += 1
    
    # Confirm to the command user
    confirm_msg = await ctx.send(f"✅ DM sent to {success_count} member(s). Failed: {failed_count}")
    await confirm_msg.delete(delay=10)

# Run the bot
bot.run(os.getenv("TOKEN"), reconnect=True)

