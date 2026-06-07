import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

queue = []

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
def play_next(ctx):
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
        ctx.voice_client.play(source, after=lambda e: play_next(ctx))
        asyncio.run_coroutine_threadsafe(
            ctx.send(f"▶️ Now playing: **{title}**"), bot.loop
        )

# ─── !play ───
@bot.command()
async def play(ctx, *, url: str):
    if not ctx.voice_client:
        await ctx.send("❌ Bot is not in a voice channel.")
        return
    queue.append(url)
    if not ctx.voice_client.is_playing():
        play_next(ctx)
        await ctx.send(f"🎵 Starting playback...")
    else:
        await ctx.send(f"➕ Added to queue. Position: **{len(queue)}**")

# ─── !pause ───
@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")
    else:
        await ctx.send("❌ Nothing is playing.")

# ─── !resume ───
@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")
    else:
        await ctx.send("❌ Nothing is paused.")

# ─── !stop ───
@bot.command()
async def stop(ctx):
    queue.clear()
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏹️ Stopped and queue cleared.")

# ─── !skip ───
@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped.")
    else:
        await ctx.send("❌ Nothing to skip.")

# ─── !showqueue ───
@bot.command()
async def showqueue(ctx):
    if not queue:
        await ctx.send("📭 Queue is empty.")
    else:
        msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queue)])
        await ctx.send(f"📋 **Queue:**\n{msg}")

# ─── !volume ───
@bot.command()
async def volume(ctx, vol: int):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source = discord.PCMVolumeTransformer(
            ctx.voice_client.source, volume=vol / 100
        )
        await ctx.send(f"🔊 Volume set to **{vol}%**")
    else:
        await ctx.send("❌ Nothing is playing.")

# ─── !join ───
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("✅ Joined your voice channel.")
    else:
        await ctx.send("❌ You are not in a voice channel.")

# ─── !leave ───
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel.")

# ─── !commands ───
@bot.command(name="commands")
async def show_commands(ctx):
    msg = """
🤖 **Bot Commands:**
`!play <youtube_url>` — Play or add to queue
`!pause` — Pause current song
`!resume` — Resume paused song
`!skip` — Skip current song
`!stop` — Stop and clear queue
`!showqueue` — Show current queue
`!volume <0-100>` — Set volume
`!join` — Join your voice channel
`!leave` — Leave voice channel
`!commands` — Show this list
    """
    await ctx.send(msg)

bot.run(TOKEN)
