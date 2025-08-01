"""Music Cog for Discord Bot - Handles music playback and queue management."""
import asyncio
import json
import logging
import os

import discord
import yt_dlp
from discord.ext import commands

log = logging.getLogger(__name__)

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
FFMPEG_OPTIONS_BASE = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''

class ConfigManager:
    """Manages JSON configuration files for each guild."""
    
    def __init__(self):
        """Initialize the config manager."""
        self.config_dir = "configs"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def _get_path(self, guild_id: int) -> str:
        """Get the config file path for a guild."""
        return os.path.join(self.config_dir, f"{guild_id}.json")
    
    def get_config(self, guild_id: int) -> dict:
        """Get the configuration for a guild."""
        config_path = self._get_path(guild_id)
        if not os.path.exists(config_path):
            default_config = {
                "volume": 75,
                "active_filter": "none",
                "queue": []
            }
            self.save_config(guild_id, default_config)
            return default_config
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_config(self, guild_id: int, data: dict):
        """Save the configuration for a guild."""
        with open(self._get_path(guild_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

class MusicControlsView(discord.ui.View):
    """A View with music control buttons."""
    
    def __init__(self, cog, *, timeout=None):
        """Initialize the music controls view."""
        super().__init__(timeout=timeout)
        self.cog = cog

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏸️")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle pause/resume button interaction."""
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            button.label = "Resume"
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
        elif vc and vc.is_paused():
            vc.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle skip button interaction."""
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message(
                "Skipped!", ephemeral=True, delete_after=5
            )
        else:
            await interaction.response.send_message(
                "Not playing anything to skip.", ephemeral=True
            )

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle stop button interaction."""
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            config = self.cog.config_manager.get_config(interaction.guild.id)
            config["queue"].clear()
            self.cog.config_manager.save_config(interaction.guild.id, config)
            await vc.disconnect()
            await interaction.response.send_message(
                "Playback stopped and queue cleared.",
                ephemeral=True,
                delete_after=10
            )
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )

class MusicCog(commands.Cog):
    """Music cog handling playback, queue management, and audio effects."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the Music cog."""
        self.bot = bot
        self.config_manager = ConfigManager()
        self.now_playing_messages = {}

    async def after_playback(self, interaction: discord.Interaction, error):
        """Callback function called after song playback ends."""
        if error:
            log.error(
                f"Error during playback in guild {interaction.guild.id}: {error}"
            )
        else:
            log.info(f"Finished playing song in guild {interaction.guild.id}.")
        await self._play_next(interaction)

    async def _cleanup_now_playing(self, guild_id: int):
        """Clean up the now playing message for a guild."""
        if guild_id in self.now_playing_messages:
            try:
                message = self.now_playing_messages[guild_id]
                view = MusicControlsView(self, timeout=1)
                for item in view.children:
                    item.disabled = True
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden):
                pass
            del self.now_playing_messages[guild_id]

    async def _play_next(self, interaction: discord.Interaction):
        """Play the next song in the queue."""
        guild_id = interaction.guild.id
        await self._cleanup_now_playing(guild_id)
        config = self.config_manager.get_config(guild_id)
        voice_client = interaction.guild.voice_client
        
        if not voice_client or not voice_client.is_connected():
            log.warning(
                f"Play_next called in guild {guild_id} but bot is not connected."
            )
            return
        
        if not config.get("queue"):
            log.info(f"Queue finished for guild {guild_id}.")
            await interaction.channel.send(
                embed=discord.Embed(
                    description="Queue finished.",
                    color=discord.Color.blue()
                )
            )
            return
        
        if voice_client.is_playing():
            log.warning(
                f"Play_next called in guild {guild_id} but already playing something."
            )
            return
        song_info = config["queue"].pop(0)
        self.config_manager.save_config(guild_id, config)
        log.info(f"Preparing to play '{song_info['title']}' in guild {guild_id}.")
        
        ffmpeg_options = FFMPEG_OPTIONS_BASE.copy()
        active_filter = config.get("active_filter", "none")
        filter_chains = {
            "bassboost": "bass=g=15,dynaudnorm=f=200",
            "nightcore": "atempo=1.3,asetrate=44100*1.3,bass=g=5",
            "slowedreverb": "atempo=0.8,aecho=0.8:0.9:1000:0.3"
        }
        
        if active_filter in filter_chains:
            ffmpeg_options['options'] += f' -af "{filter_chains[active_filter]}"'
        
        log.info(f"Guild {guild_id} - Generated FFMPEG options: {ffmpeg_options}")
        try:
            player = discord.FFmpegPCMAudio(song_info['url'], **ffmpeg_options)
            source = discord.PCMVolumeTransformer(
                player, volume=config.get("volume", 75) / 100.0
            )
            voice_client.play(
                source,
                after=lambda e: self.bot.loop.create_task(
                    self.after_playback(interaction, e)
                )
            )
            log.info(f"Playback started for '{song_info['title']}' in guild {guild_id}.")
        except Exception as e:
            log.exception(
                f"FATAL: Failed to create FFmpeg player in guild {guild_id}. "
                f"THIS IS LIKELY THE PROBLEM."
            )
            await interaction.channel.send(
                embed=discord.Embed(
                    title="Playback Error",
                    description=(
                        f"Could not start the player. The filter might be invalid "
                        f"or FFmpeg is not installed correctly.\n`{e}`"
                    ),
                    color=discord.Color.red()
                )
            )
            return
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{song_info['title']}]({song_info['webpage_url']})",
            color=discord.Color.green()
        )
        
        if song_info.get('thumbnail'):
            embed.set_thumbnail(url=song_info['thumbnail'])
        
        if active_filter != "none":
            embed.add_field(
                name="Active Filter",
                value=f"`{active_filter.capitalize()}`",
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        view = MusicControlsView(self)
        now_playing_message = await interaction.channel.send(embed=embed, view=view)
        self.now_playing_messages[guild_id] = now_playing_message

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates, particularly bot disconnections."""
        if (member.id == self.bot.user.id and 
            before.channel is not None and 
            after.channel is None):
            log.info(
                f"Bot was disconnected from voice channel in guild "
                f"{member.guild.id}. Cleaning up."
            )
            await self._cleanup_now_playing(member.guild.id)

    @discord.app_commands.command(
        name="play", 
        description="Plays a song or adds it to the queue."
    )
    async def play(self, interaction: discord.Interaction, *, query: str):
        """Play a song or add it to the queue."""
        log.info(
            f"'{interaction.user}' in guild '{interaction.guild.name}' "
            f"used /play with query: '{query}'"
        )
        
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You are not connected to a voice channel.", ephemeral=True
            )
            return
        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client
        
        if not voice_client:
            log.info(
                f"Connecting to voice channel '{voice_channel.name}' "
                f"in guild {interaction.guild.id}"
            )
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            log.info(
                f"Moving to voice channel '{voice_channel.name}' "
                f"in guild {interaction.guild.id}"
            )
            await voice_client.move_to(voice_channel)
        await interaction.response.defer()
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                search_query = (
                    f"ytsearch:{query}" if not query.startswith('http') 
                    else query
                )
                info = ydl.extract_info(search_query, download=False)
        except Exception:
            log.exception(f"yt-dlp failed to process query: '{query}'")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description="Could not process query.",
                    color=discord.Color.red()
                )
            )
            return
        config = self.config_manager.get_config(interaction.guild.id)
        embed = discord.Embed(color=discord.Color.blue())
        
        if 'entries' in info:
            count = len(info['entries'])
            log.info(
                f"Adding {count} songs from playlist '{info['title']}' "
                f"to queue in guild {interaction.guild.id}"
            )
            
            for entry in info['entries']:
                if entry:
                    song_data = {
                        'url': entry['url'],
                        'title': entry.get('title', 'Unknown Title'),
                        'thumbnail': entry.get('thumbnail'),
                        'webpage_url': entry.get('webpage_url')
                    }
                    config["queue"].append(song_data)
            
            embed.title = "Playlist Added"
            embed.description = (
                f"Added **{count} songs** from `{info['title']}` to the queue."
            )
        else:
            log.info(
                f"Adding song '{info.get('title')}' to queue "
                f"in guild {interaction.guild.id}"
            )
            
            song_data = {
                'url': info['url'],
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail'),
                'webpage_url': info.get('webpage_url')
            }
            config["queue"].append(song_data)
            
            embed.title = "Added to Queue"
            embed.description = (
                f"[{info.get('title', 'Unknown Title')}]"
                f"({info.get('webpage_url')})"
            )
        await interaction.followup.send(embed=embed)
        self.config_manager.save_config(interaction.guild.id, config)
        
        if not voice_client.is_playing():
            await self._play_next(interaction)

    async def _set_filter(
        self,
        interaction: discord.Interaction,
        filter_name: str,
        display_name: str,
        emoji: str
    ):
        """Set an audio filter for the guild."""
        log.info(
            f"'{interaction.user}' set filter to '{filter_name}' "
            f"in guild {interaction.guild.id}"
        )
        
        config = self.config_manager.get_config(interaction.guild.id)
        
        if config.get("active_filter", "none") == filter_name:
            await interaction.response.send_message(
                f"{display_name} filter is already active.", ephemeral=True
            )
            return
        
        config["active_filter"] = filter_name
        self.config_manager.save_config(interaction.guild.id, config)
        
        embed = discord.Embed(
            description=f"{emoji} **{display_name}** filter activated!",
            color=discord.Color.gold()
        )
        embed.set_footer(
            text="The effect will apply to the next song. Use /skip to apply now."
        )
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(
        name="pause", 
        description="Pauses the current song."
    )
    async def pause(self, interaction: discord.Interaction):
        """Pause the current song."""
        vc = interaction.guild.voice_client
        
        if vc and vc.is_playing():
            vc.pause()
            log.info(
                f"Playback paused in guild {interaction.guild.id} "
                f"by {interaction.user}"
            )
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback paused. ⏸️",
                    color=discord.Color.orange()
                )
            )
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )
            
    @discord.app_commands.command(
        name="resume", 
        description="Resumes the current song."
    )
    async def resume(self, interaction: discord.Interaction):
        """Resume the current song."""
        vc = interaction.guild.voice_client
        
        if vc and vc.is_paused():
            vc.resume()
            log.info(
                f"Playback resumed in guild {interaction.guild.id} "
                f"by {interaction.user}"
            )
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback resumed. ▶️",
                    color=discord.Color.green()
                )
            )
        else:
            await interaction.response.send_message(
                "Playback is not paused.", ephemeral=True
            )

    @discord.app_commands.command(
        name="stop", 
        description="Stops playback, clears queue, and leaves."
    )
    async def stop(self, interaction: discord.Interaction):
        """Stop playback, clear queue, and disconnect."""
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_connected():
            config = self.config_manager.get_config(interaction.guild.id)
            config["queue"].clear()
            self.config_manager.save_config(interaction.guild.id, config)
            await self._cleanup_now_playing(interaction.guild.id)
            await voice_client.disconnect()
            
            log.info(
                f"Playback stopped in guild {interaction.guild.id} "
                f"by {interaction.user}"
            )
            
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Playback stopped. Goodbye! 👋",
                    color=discord.Color.red()
                )
            )
        else:
            await interaction.response.send_message(
                "I'm not in a voice channel.", ephemeral=True
            )

    @discord.app_commands.command(
        name="skip", 
        description="Skips to the next song in the queue."
    )
    async def skip(self, interaction: discord.Interaction):
        """Skip to the next song in the queue."""
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            log.info(
                f"Song skipped in guild {interaction.guild.id} "
                f"by {interaction.user}"
            )
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Skipped to the next song! ⏭️",
                    color=discord.Color.blue()
                )
            )
        else:
            await interaction.response.send_message(
                "I'm not playing anything.", ephemeral=True
            )

    @discord.app_commands.command(
        name="volume", 
        description="Sets the playback volume (0-100)."
    )
    async def volume(self, interaction: discord.Interaction, level: int):
        """Set the playback volume."""
        log.info(
            f"Volume set to {level} in guild {interaction.guild.id} "
            f"by {interaction.user}"
        )
        
        if not 0 <= level <= 100:
            await interaction.response.send_message(
                "Volume must be between 0 and 100.", ephemeral=True
            )
            return
        
        config = self.config_manager.get_config(interaction.guild.id)
        config["volume"] = level
        self.config_manager.save_config(interaction.guild.id, config)
        
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.source:
            voice_client.source.volume = level / 100.0
        
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Volume set to **{level}%** 🔊",
                color=discord.Color.blue()
            )
        )

    @discord.app_commands.command(
        name="queue", 
        description="Shows the current song queue."
    )
    async def queue(self, interaction: discord.Interaction):
        """Show the current song queue."""
        log.info(
            f"Queue checked in guild {interaction.guild.id} "
            f"by {interaction.user}"
        )
        
        config = self.config_manager.get_config(interaction.guild.id)
        queue = config.get("queue", [])
        
        if not queue:
            await interaction.response.send_message(
                "The queue is empty.", ephemeral=True
            )
            return
        
        embed = discord.Embed(title="Song Queue", color=discord.Color.purple())
        queue_list = [
            f"`{i+1}.` [{song['title']}]({song['webpage_url']})"
            for i, song in enumerate(queue[:10])
        ]
        embed.description = "\n".join(queue_list)
        
        if len(queue) > 10:
            embed.set_footer(text=f"...and {len(queue) - 10} more.")
        
        await interaction.response.send_message(embed=embed)
    @discord.app_commands.command(
        name="nightcore", 
        description="Applies a nightcore (speed/pitch up) effect."
    )
    async def nightcore(self, interaction: discord.Interaction):
        """Apply nightcore effect."""
        await self._set_filter(interaction, "nightcore", "Nightcore", "🚀")
    
    @discord.app_commands.command(
        name="slowedreverb", 
        description="Applies a slowed + reverb effect."
    )
    async def slowedreverb(self, interaction: discord.Interaction):
        """Apply slowed + reverb effect."""
        await self._set_filter(interaction, "slowedreverb", "Slowed + Reverb", "🐌")
    
    @discord.app_commands.command(
        name="bassboost", 
        description="Applies a bass boost effect."
    )
    async def bassboost(self, interaction: discord.Interaction):
        """Apply bass boost effect."""
        await self._set_filter(interaction, "bassboost", "Bass Boost", "💣")
    
    @discord.app_commands.command(
        name="normal", 
        description="Clears all audio effects."
    )
    async def normal(self, interaction: discord.Interaction):
        """Clear all audio effects."""
        await self._set_filter(interaction, "none", "Normal", "✅")

async def setup(bot: commands.Bot):
    """Set up the Music cog."""
    await bot.add_cog(MusicCog(bot))
