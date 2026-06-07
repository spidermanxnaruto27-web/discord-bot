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

# ─── FIXED INTENTS ───
intents = discord.Intents.all()

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced")

bot = MyBot()
queue = []
current_song = {"title": None, "url": None}

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

# ─── NOW PLAYING EMBED + BUTTONS ───
class MusicButtons(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            button.label = "▶️ Resume"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        elif vc and vc.is_paused():
            vc.resume()
            button.label = "⏸ Pause"
            button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing to skip.", ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.guild.voice_client
        queue.clear()
        if vc:
            vc.stop()
        await interaction.response.send_message("⏹️ Stopped and queue cleared.", ephemeral=True)

    @discord.ui.button(label="📋 Queue", style=discord.ButtonStyle.secondary)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not queue:
            await interaction.response.send_message("📭 Queue is empty.", ephemeral=True)
        else:
            msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queue)])
            await interaction.response.send_message(f"📋 **Queue:**\n{msg}", ephemeral=True)

    @discord.ui.button(label="🔊 Vol +10", style=discord.ButtonStyle.secondary)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.guild.voice_client
        if vc and vc.source:
            vc.source = discord.PCMVolumeTransformer(vc.source)
            current = getattr(vc.source, 'volume', 0.8)
            new_vol = min(current + 0.1, 1.0)
            vc.source.volume = new_vol
            await interaction.response.send_message(f"🔊 Volume: **{int(new_vol*100)}%**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

# ─── NOW PLAYING EMBED ───
def now_playing_embed(title, url):
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**[{title}]({url})**",
        color=0x9B59B6
    )
    embed.add_field(name="Source", value="YouTube", inline=True)
    embed.add_field(name="Volume", value="80%", inline=True)
    embed.add_field(name="Queue", value=f"{len(queue)} waiting", inline=True)
    embed.set_footer(text="Use buttons below to control music")
    return embed

# ─── PLAY NEXT SONG ───
def play_next(guild, channel):
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

        current_song["title"] = title
        current_song["url"] = url

        source = discord.FFmpegPCMAudio(
            audio_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        )
        guild.voice_client.play(
            source, after=lambda e: play_next(guild, channel)
        )

        embed = now_playing_embed(title, url)
        view = MusicButtons(guild)
        asyncio.run_coroutine_threadsafe(
            channel.send(embed=embed, view=view), bot.loop
        )

# ─── AUTO JOIN ON STARTUP ───
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await asyncio.sleep(3)  # wait for cache to load
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel:
        try:
            await channel.connect()
            print(f"✅ Joined voice channel: {channel.name}")
        except Exception as e:
            print(f"❌ Could not join: {e}")
    else:
        print(f"❌ Channel not found! Check VOICE_CHANNEL_ID")

# ─── AUTO REJOIN IF KICKED ───
@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel is None:
        await asyncio.sleep(3)
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if channel:
            await channel.connect()
            print("🔁 Rejoined voice channel")

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
        play_next(interaction.guild, interaction.channel)
        await interaction.followup.send("🎵 Loading song...")
    else:
        await interaction.followup.send(f"➕ Added to queue! Position: **{len(queue)}**")

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

# ─── /volume ───
@bot.tree.command(name="volume", description="Set volume 0 to 100")
@app_commands.describe(level="Volume level between 0 and 100")
async def volume(interaction: discord.Interaction, level: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source = discord.PCMVolumeTransformer(
            interaction.guild.voice_client.source, volume=level / 100
        )
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")
    else:
        await interaction.response.send_message("❌ Nothing is playing.")

# ─── /commands ───
@bot.tree.command(name="commands", description="Show all bot commands")
async def show_commands(interaction: discord.Interaction):
    msg = """
🤖 **Bot Commands:**
`/play <url>` — Play YouTube song or add to queue
`/join` — Join your voice channel
`/leave` — Leave voice channel
`/volume <0-100>` — Set volume
`/commands` — Show this list

🎮 **Player Buttons:**
`⏸ Pause` — Pause or resume song
`⏭ Skip` — Skip current song
`⏹ Stop` — Stop and clear queue
`📋 Queue` — Show queue
`🔊 Vol +10` — Increase volume
    """
    await interaction.response.send_message(msg)

bot.run(TOKEN)
