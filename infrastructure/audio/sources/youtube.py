import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import yt_dlp

from domain.entities.track import Track, TrackSource
from domain.interfaces.audio_source import AudioSource

logger = logging.getLogger(__name__)


class YouTubeSource(AudioSource):
    """YouTube audio source implementation."""

    def __init__(self):
        self.ytdl_options = {
            "format": "bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
            "extract_flat": False,
            "writethumbnail": False,
            "writeinfojson": False,
        }

        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_options)

    async def search(self, query: str, max_results: int = 5) -> List[Track]:
        """Search for tracks on YouTube."""
        try:
            # Run blocking operation in thread pool
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(
                None, self._search_sync, query, max_results
            )

            tracks = []
            for entry in search_results:
                track = await self._create_track_from_entry(entry)
                if track:
                    tracks.append(track)

            logger.info(f"Found {len(tracks)} tracks for query: {query}")
            return tracks

        except Exception as e:
            logger.error(f"Error searching YouTube for '{query}': {e}")
            return []

    async def get_track_info(self, url: str, requester_id: int) -> Optional[Track]:
        """Get track information from YouTube URL."""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._extract_info_sync, url)

            if not info:
                return None

            return await self._create_track_from_entry(info, requester_id)

        except Exception as e:
            logger.error(f"Error extracting info from URL '{url}': {e}")
            return None

    async def get_stream_url(self, track: Track) -> Optional[str]:
        """Get the streaming URL for a track."""
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._extract_info_sync, track.url)

            if not info:
                return None

            # Get the best audio format URL
            formats = info.get("formats", [])
            for fmt in formats:
                if fmt.get("acodec") != "none" and fmt.get("url"):
                    return fmt["url"]

            # Fallback to direct URL
            return info.get("url")

        except Exception as e:
            logger.error(f"Error getting stream URL for track '{track.title}': {e}")
            return None

    def _search_sync(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Synchronous search operation."""
        try:
            # Use ytsearch to search YouTube
            search_query = f"ytsearch{max_results}:{query}"

            with yt_dlp.YoutubeDL(self.ytdl_options) as ytdl:
                search_results = ytdl.extract_info(search_query, download=False)

            if "entries" in search_results:
                return search_results["entries"]
            else:
                return [search_results] if search_results else []

        except Exception as e:
            logger.error(f"Sync search error: {e}")
            return []

    def _extract_info_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """Synchronous info extraction."""
        try:
            with yt_dlp.YoutubeDL(self.ytdl_options) as ytdl:
                info = ytdl.extract_info(url, download=False)
                return info

        except Exception as e:
            logger.error(f"Sync extract info error: {e}")
            return None

    async def _create_track_from_entry(
        self, entry: Dict[str, Any], requester_id: int = 0
    ) -> Optional[Track]:
        """Create a Track object from YouTube entry."""
        try:
            if not entry:
                return None

            title = entry.get("title", "Unknown Title")
            url = entry.get("webpage_url") or entry.get("url", "")
            duration = entry.get("duration", 0)
            thumbnail_url = self._get_best_thumbnail(entry.get("thumbnails", []))

            # Extract artist from title or uploader
            artist = self._extract_artist(title) or entry.get(
                "uploader", "Unknown Artist"
            )

            # Clean up title if artist was extracted
            if artist and artist in title:
                title = title.replace(f"{artist} - ", "").strip()

            track = Track(
                title=title,
                url=url,
                duration=duration or 0,
                source=TrackSource.YOUTUBE,
                requester_id=requester_id,
                thumbnail_url=thumbnail_url,
                artist=artist,
                track_id=entry.get("id"),
                metadata={
                    "view_count": entry.get("view_count"),
                    "upload_date": entry.get("upload_date"),
                    "uploader": entry.get("uploader"),
                    "like_count": entry.get("like_count"),
                },
            )

            return track

        except Exception as e:
            logger.error(f"Error creating track from entry: {e}")
            return None

    def _get_best_thumbnail(self, thumbnails: List[Dict[str, Any]]) -> Optional[str]:
        """Get the best quality thumbnail URL."""
        if not thumbnails:
            return None

        # Sort by resolution (width * height)
        sorted_thumbnails = sorted(
            thumbnails,
            key=lambda x: (x.get("width", 0) * x.get("height", 0)),
            reverse=True,
        )

        return sorted_thumbnails[0].get("url")

    def _extract_artist(self, title: str) -> Optional[str]:
        """Extract artist name from title using common patterns."""
        patterns = [
            r"^([^-]+)\s*-\s*(.+)$",  # "Artist - Song"
            r"^([^|]+)\s*\|\s*(.+)$",  # "Artist | Song"
            r"^([^:]+):\s*(.+)$",  # "Artist: Song"
        ]

        for pattern in patterns:
            match = re.match(pattern, title)
            if match:
                potential_artist = match.group(1).strip()
                # Basic validation - not too long, not all caps
                if len(potential_artist) < 50 and not potential_artist.isupper():
                    return potential_artist

        return None

    def is_supported_url(self, url: str) -> bool:
        """Check if URL is supported by this source."""
        youtube_domains = [
            "youtube.com",
            "youtu.be",
            "m.youtube.com",
            "www.youtube.com",
        ]

        return any(domain in url.lower() for domain in youtube_domains)

    def is_playlist_url(self, url: str) -> bool:
        """Check if URL is a YouTube playlist."""
        url_lower = url.lower()
        # Check for various playlist indicators
        playlist_indicators = [
            "list=",  # Regular playlists
            "playlist",  # Playlist in URL path
            "&start_radio=1",  # YouTube Mix/Radio
            "rdmm",  # YouTube Mix identifier
            "rd",  # Radio playlist identifier
        ]

        has_playlist_indicator = any(
            indicator in url_lower for indicator in playlist_indicators
        )
        logger.debug(f"Playlist URL check for {url}: {has_playlist_indicator}")
        return has_playlist_indicator

    async def get_playlist_info(
        self, playlist_url: str, requester_id: int, max_tracks: int = 50
    ) -> List[Track]:
        """Extract tracks from a YouTube playlist."""
        try:
            logger.info(f"Starting playlist extraction from: {playlist_url}")
            logger.info(
                f"Max tracks requested: {max_tracks}, Requester: {requester_id}"
            )

            # Create playlist-specific options
            playlist_options = self.ytdl_options.copy()
            playlist_options["noplaylist"] = False  # Enable playlist extraction
            playlist_options["playlistend"] = max_tracks  # Limit playlist size
            playlist_options["extract_flat"] = False  # Get full info for each entry

            # Special handling for YouTube Mix/Radio playlists
            if (
                "start_radio=1" in playlist_url
                or "rdmm" in playlist_url.lower()
                or ("rd" in playlist_url and "list=rd" in playlist_url)
            ):
                logger.info(
                    "Detected YouTube Mix/Radio playlist, using special extraction options"
                )
                playlist_options["playlistreverse"] = False
                playlist_options["playlistrandom"] = False
                # Mix playlists are dynamically generated, so we might need to be more lenient
                playlist_options["ignoreerrors"] = True
                playlist_options["extract_flat"] = False

            logger.debug(f"Playlist extraction options: {playlist_options}")

            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, self._extract_playlist_sync, playlist_url, playlist_options
            )

            if not info:
                logger.error(f"No info extracted from playlist: {playlist_url}")
                return []

            logger.debug(f"Extracted info keys: {list(info.keys())}")
            logger.info(f"Playlist title: {info.get('title', 'Unknown')}")
            logger.info(f"Playlist uploader: {info.get('uploader', 'Unknown')}")

            tracks = []
            entries = info.get("entries", [])

            if not entries:
                logger.warning(f"No entries found in playlist: {playlist_url}")
                logger.debug(f"Info structure: {info}")

                # Fallback for Mix/Radio playlists: try to extract the current video
                if "start_radio=1" in playlist_url or "rdmm" in playlist_url.lower():
                    logger.info("Attempting fallback extraction for Mix playlist")
                    try:
                        # Extract the video ID from the URL to get just the current track
                        import re

                        video_id_match = re.search(r"[?&]v=([^&]+)", playlist_url)
                        if video_id_match:
                            video_id = video_id_match.group(1)
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            logger.info(f"Extracting fallback track: {video_url}")

                            fallback_track = await self.get_track_info(
                                video_url, requester_id
                            )
                            if fallback_track:
                                logger.info(
                                    "Successfully extracted fallback track from Mix playlist"
                                )
                                return [fallback_track]
                    except Exception as e:
                        logger.error(f"Fallback extraction failed: {e}")

                return []

            logger.info(f"Found {len(entries)} entries in playlist")

            # Process each entry in the playlist
            for i, entry in enumerate(entries):
                if entry is None:  # Skip unavailable videos
                    logger.debug(f"Entry {i + 1} is None, skipping")
                    continue

                logger.debug(
                    f"Processing entry {i + 1}: {entry.get('title', 'Unknown Title')}"
                )

                try:
                    track = await self._create_track_from_entry(entry, requester_id)
                    if track:
                        tracks.append(track)
                        logger.debug(f"Successfully created track: {track.title}")
                    else:
                        logger.debug(f"Failed to create track from entry {i + 1}")

                except Exception as e:
                    logger.warning(f"Failed to process playlist entry {i + 1}: {e}")
                    logger.debug(f"Entry data: {entry}")
                    continue

            logger.info(f"Successfully processed {len(tracks)} tracks from playlist")
            return tracks

        except Exception as e:
            logger.error(f"Error extracting playlist from '{playlist_url}': {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def _extract_playlist_sync(
        self, url: str, options: dict
    ) -> Optional[Dict[str, Any]]:
        """Synchronous playlist extraction."""
        try:
            with yt_dlp.YoutubeDL(options) as ytdl:
                info = ytdl.extract_info(url, download=False)
                return info

        except Exception as e:
            logger.error(f"Sync extract playlist error: {e}")
            return None
