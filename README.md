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
```

### 3. Run
```bash
docker-compose up -d
```

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
├── presentation/          # Discord cogs
└── utils/                 # Utilities & validators
```

Built with Clean Architecture, SQLAlchemy, Redis caching, and enterprise patterns.