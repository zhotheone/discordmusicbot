# Discord Music Bot - Enhanced Edition

A feature-rich Discord music bot with advanced audio processing, multiple simultaneous filters, and runtime configuration capabilities.

## 🚀 Key Features

### Core Music Functionality
- 🎵 **YouTube Integration** - Play music from URLs or search queries
- 📋 **Advanced Queue Management** - Queue songs with repeat modes
- ⏯️ **Smart Playback Controls** - Pause, resume, skip, stop with interactive buttons
- 🔁 **Flexible Repeat Modes** - Off, single song, or entire queue
- 🎚️ **Volume Control** - Adjustable volume from 0-150%

### 🎛️ Advanced Audio Filter System

#### Multiple Simultaneous Filters
- **Apply multiple filters at once** for complex audio processing
- **Runtime configuration** - adjust parameters without restarting
- **Real-time FFmpeg filter chain generation**
- **Per-guild filter persistence** - settings saved automatically

#### Available Filters

| Filter | Description | Configurable Parameters |
|--------|-------------|------------------------|
| **Bass Boost** | Enhance low-frequency sounds | Gain (0-30 dB), Frequency (100-500 Hz) |
| **Nightcore** | Speed up and pitch up audio | Tempo (1.0-2.0x), Pitch Factor (1.0-2.0x), Bass Compensation |
| **Slowed + Reverb** | Slow down with echo effects | Tempo (0.5-1.0x), Echo parameters (gain, delay, decay) |
| **8D Audio** | Create surround sound effect | Pulsation frequency (0.1-2.0 Hz) |
| **3-Band Equalizer** | Frequency-specific adjustments | Low/Mid/High frequency centers and gains |
| **Distortion** | Add overdrive/distortion | Gain (1-20), Harmonic color (1-100) |
| **Compressor** | Dynamic range compression | Threshold, ratio, attack/release times |

#### Filter Presets
- **Gaming** - Optimized for game audio with voice clarity
- **Music** - Enhanced music listening with bass boost and EQ
- **Vocal** - Optimized for podcasts and voice content

### 📱 Interactive Controls

#### Enhanced Music Control Panel
- ⏸️ **Pause/Resume** - Toggle playback
- ⏭️ **Skip** - Jump to next song
- ⏹️ **Stop** - Stop playback and clear queue
- 🔁 **Repeat Toggle** - Cycle through repeat modes
- 🎛️ **Filter Manager** - Interactive filter control panel

#### Filter Management UI
- **Multi-select dropdown** - Enable/disable multiple filters
- **Preset application** - Quick setup with predefined configurations  
- **Real-time status** - View active filters and parameters
- **Parameter visualization** - See generated FFmpeg filter chains

## 🛠️ Installation & Setup

### Quick Start with Docker (Recommended)

1. **Clone the repository**
2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```
3. **Add your Discord bot token** to `.env`:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```
4. **Start the bot**:
   ```bash
   docker-compose up -d
   ```

### Manual Installation

#### Prerequisites
- Python 3.10+
- FFmpeg (required for audio processing)
- Discord bot token

#### Steps
1. **Install FFmpeg**:
   - Ubuntu/Debian: `sudo apt install ffmpeg`
   - macOS: `brew install ffmpeg` 
   - Windows: Download from [FFmpeg website](https://ffmpeg.org/)

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your bot token
   ```

4. **Run the bot**:
   ```bash
   python main.py
   ```

## 🎮 Command Reference

### Basic Music Commands
- `/play <song/url>` - Play a song or add to queue
- `/pause` - Pause current song
- `/resume` - Resume playback  
- `/skip` - Skip to next song
- `/stop` - Stop playback and clear queue
- `/queue` - Show current queue
- `/volume <0-150>` - Set playback volume

### Legacy Audio Effects (Simple)
- `/bassboost` - Toggle bass boost
- `/nightcore` - Toggle nightcore effect
- `/slowed` - Toggle slowed effect
- `/8d` - Toggle 8D audio
- `/repeat` - Cycle repeat modes

### 🎛️ Advanced Filter Commands

#### Filter Management
- `/filter_list` - List all available filters
- `/filter_enable <name>` - Enable a specific filter
- `/filter_disable <name>` - Disable a specific filter
- `/filter_clear` - Disable all active filters
- `/filter_status` - Show current filter status

#### Runtime Configuration
- `/filter_configure <filter> <parameter> <value>` - Adjust filter parameters
- `/filter_info <name>` - Get detailed filter information

#### Presets
- `/preset_list` - List available presets
- `/preset_apply <name>` - Apply a filter preset

### 🎛️ Filter Configuration Examples

```bash
# Enable bass boost with custom settings
/filter_enable bassboost
/filter_configure bassboost gain 20
/filter_configure bassboost frequency 150

# Apply nightcore with slower tempo
/filter_enable nightcore  
/filter_configure nightcore tempo 1.2
/filter_configure nightcore pitch_factor 1.1

# Use 3-band equalizer
/filter_enable equalizer
/filter_configure equalizer gain1 5    # Boost bass
/filter_configure equalizer gain2 2    # Slight mid boost  
/filter_configure equalizer gain3 -2   # Reduce treble

# Apply gaming preset then fine-tune
/preset_apply gaming
/filter_configure compressor threshold 0.4
```

### 🎵 Creating Custom Filter Combinations

You can combine multiple filters for unique audio effects:

```bash
# Ambient/Chill Setup
/filter_enable slowed
/filter_enable compressor  
/filter_configure slowed tempo 0.85
/filter_configure compressor ratio 2

# Bass-Heavy Gaming Setup
/filter_enable bassboost
/filter_enable compressor
/filter_enable equalizer
/filter_configure bassboost gain 25
/filter_configure equalizer freq1 80
/filter_configure equalizer gain1 8
```

## 🎛️ Interactive Filter Management

The enhanced music control panel includes a **Filters** button that opens an interactive interface:

1. **Multi-select Dropdown** - Check/uncheck filters to enable/disable
2. **Apply Preset** - Quick access to predefined configurations
3. **Clear All** - Remove all active filters
4. **Status** - View current settings and generated filter chain

## 🏗️ Technical Architecture

### Filter System Design
- **Modular Architecture** - Each filter is independently configurable
- **Parameter Validation** - Range checking for all parameters
- **FFmpeg Integration** - Dynamic filter chain generation
- **State Persistence** - Per-guild settings saved to JSON
- **Real-time Updates** - Changes apply to next song automatically

### File Structure
```
├── main.py                    # Bot entry point
├── cogs/
│   ├── playback_cog.py       # Music playback with enhanced filters
│   ├── effects_cog.py        # Legacy effects (backward compatibility)
│   └── advanced_effects_cog.py # Advanced filter management
├── utils/
│   ├── config_manager.py     # Guild configuration management  
│   ├── advanced_filters.py   # Filter system core
│   ├── advanced_views.py     # Enhanced UI components
│   ├── views.py             # Basic UI components
│   └── filters.py           # Legacy filter definitions
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker Compose setup
└── requirements.txt         # Python dependencies
```

## 🐳 Docker Configuration

The included Docker setup provides:
- **FFmpeg pre-installed** - No manual installation required
- **Volume persistence** - Configs and logs preserved
- **Resource limits** - Configurable CPU/memory limits
- **Health checks** - Automatic restart on failure
- **Logging** - Structured log output with rotation

## 🔧 Troubleshooting

### Common Issues

**Filter not applying to current song**
- Use `/skip` to apply filter changes to current playback

**Multiple filters causing audio distortion**  
- Reduce individual filter intensities
- Use `/filter_clear` to reset and start over

**Bot not responding to filter commands**
- Check bot has proper permissions in voice channels
- Verify FFmpeg is installed (automatic in Docker)

**Parameter out of range errors**
- Use `/filter_info <name>` to see valid parameter ranges
- Each filter has different acceptable values

### Docker Issues

**Container won't start**
```bash
docker-compose logs discord-music-bot
```

**Permission issues**
```bash
sudo chown -R $USER:$USER .
```

**Rebuild after updates**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🎯 Advanced Usage Tips

1. **Combine complementary filters** - Bass boost + compressor works well
2. **Use presets as starting points** - Apply preset then fine-tune parameters  
3. **Test with different music genres** - Electronic music handles more processing
4. **Monitor CPU usage** - Multiple heavy filters can impact performance
5. **Save custom combinations** - Note successful parameter combinations

## 🤝 Bot Setup & Permissions

### Discord Developer Portal Setup
1. Create application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create bot and copy token to `.env` file
3. Generate invite link with these permissions:
   - Send Messages
   - Use Slash Commands  
   - Connect
   - Speak
   - Use Voice Activity
   - Embed Links

### Required Permissions
The bot needs voice channel permissions to function properly. Make sure it can:
- Join voice channels
- Speak in voice channels  
- Send messages in text channels
- Use application commands

## 📝 License

This project is open source. Feel free to modify and distribute.

---

## 🎵 Happy Listening!

Enjoy your enhanced Discord music experience with professional-grade audio processing!


Code Duplication: Multiple ConfigManager implementations in different files
Shared State Issues: Each cog creates separate instances of managers, causing inconsistency
Tight Coupling: Direct dependency instantiation instead of injection
Scalability Limitations: JSON file storage won't scale
Monolithic Cogs: Large files mixing multiple responsibilities
No Service Layer: Business logic mixed with Discord command handling
