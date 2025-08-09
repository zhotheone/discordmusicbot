# 🎵 Discord Music Bot

Enterprise-grade Discord music bot with YouTube, Spotify integration, audio filters, and user preferences.

## 🚀 Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env and add your Discord bot token
nano .env

# 3. Start all services
docker-compose up -d

# 4. Check logs
docker-compose logs -f discord-music-bot
```

## ⚙️ Features

- ✅ **Play/Stop/Skip/Pause/Resume** commands
- ✅ **YouTube & Spotify** integration with search
- ✅ **Audio Filters**: Bass boost, Reverb, 8D, Slow/Speed
- ✅ **User Settings**: Volume, filters, repeat preferences
- ✅ **Queue Management**: Add, remove, shuffle, repeat modes
- ✅ **History Tracking**: User listening history
- ✅ **Database**: PostgreSQL with SQLAlchemy + Alembic
- ✅ **Caching**: Redis for performance
- ✅ **Slash Commands**: Modern Discord interactions
- ✅ **Telegram Bridge (optional)**: Control the bot from Telegram and mirror playback updates to a linked chat

## 🛠️ Setup

### 1. Discord Bot
1. Create application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create bot user and copy token
3. Add bot to server with permissions: `View Channels`, `Send Messages`, `Connect`, `Speak`, `Use Slash Commands`

### 2. Configuration
Edit `.env` file:
```bash
DISCORD_TOKEN=your_discord_bot_token_here
COMMAND_PREFIX=/

# Optional Spotify integration
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Optional Telegram bridge
ENABLE_TELEGRAM=true
TELEGRAM_TOKEN=your_telegram_bot_token_here
```

### 3. Run
```bash
docker-compose up -d
```

### Telegram Bridge (optional)

Enable a Telegram bot to control playback and receive notifications from Discord:

1) Create a bot with @BotFather and copy the token.
2) In `.env`, set:
	- `ENABLE_TELEGRAM=true`
	- `TELEGRAM_TOKEN=<your_bot_token>`
3) Add your Telegram bot to the target group/channel where you want messages.
4) Get the chat ID: in that chat, send `/id` to the bot (after it’s added) and copy the `chat_id`.
5) In Discord (Admin), run the slash command to link the server to the Telegram chat:
	- `/connect_telegram <chat_id>`
6) Restart the bot if needed: `docker-compose up -d --build`

What you get:
- Playback events mirrored to Telegram (now playing, skipped, finished, paused/resumed, volume changes, queue finished)
- Control from Telegram with commands below
- From Discord, admins can ping everyone in the linked Telegram chat with `/all <reason>`
## 🎮 Commands

```
/play <song/url>     - Play music from YouTube or Spotify
/skip               - Skip current track
/stop               - Stop playback
/pause              - Pause playback
/resume             - Resume playback
/queue              - Show current queue
/volume <0-100>     - Set volume
/repeat <off/track/queue> - Set repeat mode
/nowplaying         - Show current track
```

### Telegram commands

```
/list                - List non-offline users in the linked Discord server
/play <query|url>    - Queue a track on the linked Discord server
/queue               - Show the current playback queue
/stop                - Stop playback and disconnect
/volume <0-100>      - Set playback volume
/id                  - Print your Telegram user_id and chat_id (use chat_id to link)
```

Admin (Discord) helpers:
- `/connect_telegram <chat_id>` — link this guild to a Telegram chat
- `/all <reason>` — mention all known humans in the linked Telegram chat

## 🗄️ Services

| Service | Port | Purpose |
|---------|------|---------|
| Bot | - | Discord Music Bot |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |

## 📊 Monitoring

```bash
# View logs
docker-compose logs -f discord-music-bot

# Check service status
docker-compose ps

# Access database
docker-compose exec postgres psql -U musicbot -d musicbot

# Access Redis
docker-compose exec redis redis-cli
```

## 🔄 Updates

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build
```

## 📁 Architecture

```
├── main.py                 # Entry point
├── config/                 # Settings & database
├── core/                   # Bot, DI, events
├── domain/                 # Business logic
├── infrastructure/         # Database, audio, cache
├── application/           # Commands & handlers
├── presentation/          # Discord cogs + Telegram service
└── utils/                 # Utilities & validators
```

Built with Clean Architecture, SQLAlchemy, Redis caching, and enterprise patterns.