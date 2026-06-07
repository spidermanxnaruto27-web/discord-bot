import discord
from discord import app_commands
import yt_dlp
import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced")

bot = MyBot()
queue = []

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
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel:
        await channel.connect()
        print(f"✅ Joined voice channel: {channel.name}")

# ─── AUTO REJOIN IF KICKED ───
@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel is None:
        await asyncio.sleep(3)
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if channel:
            await channel.connect()
            print("🔁 Rejoined voice channel")

# ─── PLAY NEXT SONG IN QUEUE ───
def play_next(interaction):
    if len(queue) > 0:
        url = queue.pop(0)
        ydl_opts = {
            "format": "bestaudio",
            "quiet": True,
            "cookiefile": "cookies.txt"
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]
            title = info.get("title", "Unknown")
        source = discord.FFmpegPCMAudio(
            audio_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        )
        interaction.guild.voice_client.play(
            source, after=lambda e: play_next(interaction)
        )
        asyncio.run_coroutine_threadsafe(
            interaction.channel.send(f"▶️ Now playing: **{title}**"), bot.loop
        )

# ─── /play ───
@bot.tree.command(name="play", description="Play a YouTube song or add to queue")
@app_commands.describe(url="YouTube video URL")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    if not interaction.guild.voice_client:
        await interaction.followup.send("❌ Bot is not in a voice channel.")
        return
    queue.append(url)
    if not interaction.guild.voice_client.is_playing():
        play_next(interaction)
        await interaction.followup.send("🎵 Starting playback...")
    else:
        await interaction.followup.send(f"➕ Added to queue. Position: **{len(queue)}**")

# ─── /pause ───
@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️ Paused.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.")

# ─── /resume ───
@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("❌ Nothing is paused.")

# ─── /stop ───
@bot.tree.command(name="stop", description="Stop music and clear queue")
async def stop(interaction: discord.Interaction):
    queue.clear()
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Stopped and queue cleared.")
    else:
        await interaction.response.send_message("❌ Bot is not in a voice channel.")

# ─── /skip ───
@bot.tree.command(name="skip", description="Skip current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped.")
    else:
        await interaction.response.send_message("❌ Nothing to skip.")

# ─── /queue ───
@bot.tree.command(name="queue", description="Show current song queue")
async def showqueue(interaction: discord.Interaction):
    if not queue:
        await interaction.response.send_message("📭 Queue is empty.")
    else:
        msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queue)])
        await interaction.response.send_message(f"📋 **Queue:**\n{msg}")

# ─── /volume ───
@bot.tree.command(name="volume", description="Set volume (0 to 100)")
@app_commands.describe(level="Volume level between 0 and 100")
async def volume(interaction: discord.Interaction, level: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source = discord.PCMVolumeTransformer(
            interaction.guild.voice_client.source, volume=level / 100
        )
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")
    else:
        await interaction.response.send_message("❌ Nothing is playing.")

# ─── /join ───
@bot.tree.command(name="join", description="Bot joins your voice channel")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("✅ Joined your voice channel.")
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

# ─── /commands ───
@bot.tree.command(name="commands", description="Show all bot commands")
async def show_commands(interaction: discord.Interaction):
    msg = """
🤖 **Bot Commands:**
`/play <url>` — Play YouTube song or add to queue
`/pause` — Pause current song
`/resume` — Resume paused song
`/skip` — Skip current song
`/stop` — Stop and clear queue
`/queue` — Show current queue
`/volume <0-100>` — Set volume
`/join` — Join your voice channel
`/leave` — Leave voice channel
`/commands` — Show this list
    """
    await interaction.response.send_message(msg)

bot.run(TOKEN)
