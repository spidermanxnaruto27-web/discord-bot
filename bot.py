import discord
from discord import app_commands
import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

intents = discord.Intents.all()

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced")

bot = MyBot()

# ─── KEEP RENDER ALIVE ───
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# ─── AUTO JOIN ON STARTUP ───
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await asyncio.sleep(3)
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel:
        try:
            await channel.connect()
            print(f"✅ Joined: {channel.name}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("❌ Channel not found! Check VOICE_CHANNEL_ID")

# ─── AUTO REJOIN IF KICKED ───
@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel is None:
        await asyncio.sleep(3)
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if channel:
            await channel.connect()
            print("🔁 Rejoined voice channel")

# ─── /join ───
@bot.tree.command(name="join", description="Bot joins your voice channel")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        await interaction.response.send_message(f"✅ Joined **{channel.name}**")
    else:
        await interaction.response.send_message("❌ You are not in a voice channel.")

# ─── /leave ───
@bot.tree.command(name="leave", description="Bot leaves the voice channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Left the voice channel.")
    else:
        await interaction.response.send_message("❌ Bot is not in a voice channel.")

bot.run(TOKEN)
