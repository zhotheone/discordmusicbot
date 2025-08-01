import discord
from discord.ext import commands
import yt_dlp
import logging
from utils.config_manager import ConfigManager
from utils.views import MusicControlsView
from utils.filters import FFMPEG_FILTER_CHAINS

log = logging.getLogger(__name__)

YTDL_OPTIONS = { 'format': 'bestaudio/best', 'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s', 'restrictfilenames': True, 'noplaylist': False, 'nocheckcertificate': True, 'ignoreerrors': False, 'logtostderr': False, 'quiet': True, 'no_warnings': True, 'default_search': 'auto', 'source_address': '0.0.0.0' }
FFMPEG_OPTIONS_BASE = { 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn' }
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''

class PlaybackCog(commands.Cog, name="Playback Controls"):
    """Commands to play, stop, and manage the music queue."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_manager = ConfigManager()
        self.now_playing_messages = {}

    async def stop_player(self, guild):
        """A helper to fully stop playback and cleanup."""
        vc = guild.voice_client
        if vc:
            vc.stop()
        config = self.config_manager.get_config(guild.id)
        config["queue"].clear()
        self.config_manager.save_config(guild.id, config)
        await self._cleanup_now_playing(guild.id)
        if vc and vc.is_connected():
            await vc.disconnect()

    async def after_playback(self, interaction: discord.Interaction, error):
        if error:
            log.error(f"Error during playback in guild {interaction.guild.id}: {error}")
        else:
            log.info(f"Finished playing song in guild {interaction.guild.id}.")
        await self._play_next(interaction)

    async def _cleanup_now_playing(self, guild_id: int):
        if guild_id in self.now_playing_messages:
            try:
                message = self.now_playing_messages[guild_id]
                view = MusicControlsView(self, timeout=1)
                for item in view.children: item.disabled = True
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden): pass
            del self.now_playing_messages[guild_id]

    async def _play_next(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        await self._cleanup_now_playing(guild_id)
        config = self.config_manager.get_config(guild_id)
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected(): return
        if not config.get("queue"):
            await interaction.channel.send(embed=discord.Embed(description="Queue finished.", color=discord.Color.blue())); return
        if vc.is_playing() or vc.is_paused(): return

        song_info = config["queue"].pop(0)
        self.config_manager.save_config(guild_id, config)
        log.info(f"Preparing to play '{song_info['title']}' in guild {guild_id}.")

        ffmpeg_options = FFMPEG_OPTIONS_BASE.copy()
        active_filter = config.get("active_filter", "none")
        if active_filter in FFMPEG_FILTER_CHAINS:
            ffmpeg_options['options'] += f' -af "{FFMPEG_FILTER_CHAINS[active_filter]}"'
        
        log.info(f"Guild {guild_id} - Generated FFMPEG options: {ffmpeg_options}")

        try:
            player = discord.FFmpegPCMAudio(song_info['url'], **ffmpeg_options)
            source = discord.PCMVolumeTransformer(player, volume=config.get("volume", 75) / 100.0)
            vc.play(source, after=lambda e: self.bot.loop.create_task(self.after_playback(interaction, e)))
        except Exception:
            log.exception(f"Failed to create FFmpeg player in guild {guild_id}.")
            await interaction.channel.send(embed=discord.Embed(title="Playback Error", color=discord.Color.red())); return

        embed = discord.Embed(title="Now Playing", description=f"[{song_info['title']}]({song_info['webpage_url']})", color=discord.Color.green())
        if song_info.get('thumbnail'): embed.set_thumbnail(url=song_info['thumbnail'])
        if active_filter != "none": embed.add_field(name="Active Filter", value=f"`{active_filter.capitalize()}`", inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        view = MusicControlsView(self)
        now_playing_message = await interaction.channel.send(embed=embed, view=view)
        self.now_playing_messages[guild_id] = now_playing_message

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            await self._cleanup_now_playing(member.guild.id)

    @discord.app_commands.command(name="play", description="Plays a song or adds it to the queue.")
    async def play(self, interaction: discord.Interaction, *, query: str):
        if not interaction.user.voice:
            await interaction.response.send_message("You are not connected to a voice channel.", ephemeral=True); return
        
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        await interaction.response.defer()

        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl: info = ydl.extract_info(f"ytsearch:{query}" if not query.startswith('http') else query, download=False)
        except Exception:
            log.exception(f"yt-dlp failed to process query: '{query}'")
            await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Could not process query.", color=discord.Color.red())); return

        config = self.config_manager.get_config(interaction.guild.id)
        embed = discord.Embed(color=discord.Color.blue())
        
        if 'entries' in info:
            for entry in info['entries']:
                if entry: config["queue"].append({'url': entry['url'], 'title': entry.get('title', 'Unknown Title'), 'thumbnail': entry.get('thumbnail'), 'webpage_url': entry.get('webpage_url')})
            embed.title = "Playlist Added"; embed.description = f"Added **{len(info['entries'])} songs** from `{info['title']}`"
        else:
            config["queue"].append({'url': info['url'], 'title': info.get('title', 'Unknown Title'), 'thumbnail': info.get('thumbnail'), 'webpage_url': info.get('webpage_url')})
            embed.title = "Added to Queue"; embed.description = f"[{info.get('title', 'Unknown Title')}]({info.get('webpage_url')})"
        
        await interaction.followup.send(embed=embed)
        self.config_manager.save_config(interaction.guild.id, config)

        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction)

    @discord.app_commands.command(name="pause", description="Pauses the current song.")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message(embed=discord.Embed(description="Playback paused. ⏸️", color=discord.Color.orange()))
        else: await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            
    @discord.app_commands.command(name="resume", description="Resumes the current song.")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message(embed=discord.Embed(description="Playback resumed. ▶️", color=discord.Color.green()))
        else: await interaction.response.send_message("Playback is not paused.", ephemeral=True)
            
    @discord.app_commands.command(name="stop", description="Stops playback, clears queue, and leaves.")
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await self.stop_player(interaction.guild)
            await interaction.response.send_message(embed=discord.Embed(description="Playback stopped. Goodbye! 👋", color=discord.Color.red()))
        else: await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
    
    @discord.app_commands.command(name="skip", description="Skips to the next song in the queue.")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message(embed=discord.Embed(description="Skipped to the next song! ⏭️", color=discord.Color.blue()))
        else: await interaction.response.send_message("I'm not playing anything.", ephemeral=True)

    @discord.app_commands.command(name="queue", description="Shows the current song queue.")
    async def queue(self, interaction: discord.Interaction):
        config = self.config_manager.get_config(interaction.guild.id)
        queue = config.get("queue", [])
        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True); return
        embed = discord.Embed(title="Song Queue", color=discord.Color.purple())
        queue_list = [f"`{i+1}.` [{song['title']}]({song['webpage_url']})" for i, song in enumerate(queue[:10])]
        embed.description = "\n".join(queue_list)
        if len(queue) > 10: embed.set_footer(text=f"...and {len(queue) - 10} more.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlaybackCog(bot))
