import logging
import re
from typing import Any, Dict, List, Optional

import aiohttp

from domain.entities.track import Track, TrackSource
from domain.interfaces.audio_source import AudioSource
from infrastructure.audio.sources.youtube import YouTubeSource

logger = logging.getLogger(__name__)


class SpotifySource(AudioSource):
    """Spotify integration that uses YouTube for actual audio streaming."""

    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        self.youtube_source = YouTubeSource()

    async def search(self, query: str, max_results: int = 5) -> List[Track]:
        """Search for tracks on Spotify and get YouTube equivalents."""
        try:
            if not self.client_id or not self.client_secret:
                logger.warning(
                    "Spotify credentials not configured, falling back to YouTube"
                )
                return await self.youtube_source.search(query, max_results)

            # Ensure we have a valid access token
            await self._ensure_access_token()

            # Search Spotify
            spotify_tracks = await self._search_spotify(query, max_results)

            # Convert to YouTube tracks
            tracks = []
            for spotify_track in spotify_tracks:
                youtube_track = await self._find_youtube_equivalent(spotify_track)
                if youtube_track:
                    # Update track with Spotify metadata
                    youtube_track.source = TrackSource.SPOTIFY
                    youtube_track.metadata.update(
                        {
                            "spotify_id": spotify_track.get("id"),
                            "popularity": spotify_track.get("popularity"),
                            "explicit": spotify_track.get("explicit"),
                        }
                    )
                    tracks.append(youtube_track)

            logger.info(
                f"Found {len(tracks)} Spotify->YouTube tracks for query: {query}"
            )
            return tracks

        except Exception as e:
            logger.error(f"Error searching Spotify for '{query}': {e}")
            # Fallback to YouTube search
            return await self.youtube_source.search(query, max_results)

    async def get_track_info(self, url: str, requester_id: int) -> Optional[Track]:
        """Get track information from Spotify URL."""
        try:
            if not self.is_supported_url(url):
                return None

            # Extract Spotify track ID from URL
            track_id = self._extract_track_id(url)
            if not track_id:
                return None

            # Ensure we have a valid access token
            await self._ensure_access_token()

            # Get track info from Spotify
            spotify_track = await self._get_spotify_track(track_id)
            if not spotify_track:
                return None

            # Find YouTube equivalent
            youtube_track = await self._find_youtube_equivalent(
                spotify_track, requester_id
            )
            if youtube_track:
                # Update with Spotify metadata
                youtube_track.source = TrackSource.SPOTIFY
                youtube_track.metadata.update(
                    {
                        "spotify_id": spotify_track.get("id"),
                        "popularity": spotify_track.get("popularity"),
                        "explicit": spotify_track.get("explicit"),
                        "original_spotify_url": url,
                    }
                )

            return youtube_track

        except Exception as e:
            logger.error(f"Error extracting info from Spotify URL '{url}': {e}")
            return None

    async def get_stream_url(self, track: Track) -> Optional[str]:
        """Get streaming URL (delegates to YouTube)."""
        return await self.youtube_source.get_stream_url(track)

    async def _ensure_access_token(self) -> None:
        """Ensure we have a valid Spotify access token."""
        import time

        if (
            self.access_token
            and self.token_expires_at
            and time.time() < self.token_expires_at
        ):
            return

        await self._get_access_token()

    async def _get_access_token(self) -> None:
        """Get Spotify access token using client credentials."""
        try:
            import base64
            import time

            # Prepare auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {credentials_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {"grant_type": "client_credentials"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://accounts.spotify.com/api/token", headers=headers, data=data
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = (
                            time.time() + expires_in - 60
                        )  # 60s buffer
                        logger.info("Successfully obtained Spotify access token")
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to get Spotify token: {response.status} - {error_text}"
                        )
                        raise Exception(f"Spotify auth failed: {response.status}")

        except Exception as e:
            logger.error(f"Error getting Spotify access token: {e}")
            raise

    async def _search_spotify(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Spotify for tracks."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"q": query, "type": "track", "limit": limit, "market": "US"}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.spotify.com/v1/search", headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("tracks", {}).get("items", [])
                    else:
                        logger.error(f"Spotify search failed: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error searching Spotify: {e}")
            return []

    async def _get_spotify_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Get track details from Spotify."""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.spotify.com/v1/tracks/{track_id}", headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Spotify track fetch failed: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error getting Spotify track: {e}")
            return None

    async def _find_youtube_equivalent(
        self, spotify_track: Dict[str, Any], requester_id: int = 0
    ) -> Optional[Track]:
        """Find YouTube equivalent of Spotify track."""
        try:
            # Build search query from Spotify track
            title = spotify_track.get("name", "")
            artists = [
                artist.get("name", "") for artist in spotify_track.get("artists", [])
            ]
            artist_str = ", ".join(artists)

            # Try different search variations
            search_queries = [
                f"{artist_str} - {title}",
                f"{artist_str} {title}",
                f"{title} {artist_str}",
                title,  # fallback
            ]

            for query in search_queries:
                youtube_tracks = await self.youtube_source.search(query, max_results=3)

                if youtube_tracks:
                    # Find best match based on title similarity
                    best_match = self._find_best_match(
                        title,
                        artist_str,
                        youtube_tracks,
                        spotify_track.get("duration_ms", 0) / 1000,
                    )

                    if best_match:
                        # Update with Spotify metadata
                        best_match.artist = artist_str
                        best_match.album = spotify_track.get("album", {}).get("name")
                        best_match.requester_id = requester_id

                        # Add thumbnail from Spotify if available
                        album_images = spotify_track.get("album", {}).get("images", [])
                        if album_images:
                            best_match.thumbnail_url = album_images[0].get("url")

                        return best_match

            logger.warning(
                f"Could not find YouTube equivalent for: {artist_str} - {title}"
            )
            return None

        except Exception as e:
            logger.error(f"Error finding YouTube equivalent: {e}")
            return None

    def _find_best_match(
        self,
        target_title: str,
        target_artist: str,
        candidates: List[Track],
        target_duration: float,
    ) -> Optional[Track]:
        """Find the best matching track from candidates."""
        if not candidates:
            return None

        def similarity_score(track: Track) -> float:
            score = 0.0

            # Title similarity
            title_similarity = self._text_similarity(
                target_title.lower(), track.title.lower()
            )
            score += title_similarity * 0.5

            # Artist similarity
            if track.artist:
                artist_similarity = self._text_similarity(
                    target_artist.lower(), track.artist.lower()
                )
                score += artist_similarity * 0.3

            # Duration similarity (if both have duration)
            if target_duration > 0 and track.duration > 0:
                duration_diff = abs(target_duration - track.duration) / max(
                    target_duration, track.duration
                )
                duration_score = max(
                    0, 1 - duration_diff * 2
                )  # Penalize large differences
                score += duration_score * 0.2

            return score

        # Find candidate with highest similarity score
        best_candidate = max(candidates, key=similarity_score)

        # Only return if similarity is reasonable
        if similarity_score(best_candidate) > 0.4:
            return best_candidate

        return None

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        if not text1 or not text2:
            return 0.0

        # Simple word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _extract_track_id(self, url: str) -> Optional[str]:
        """Extract Spotify track ID from URL."""
        patterns = [
            r"spotify\.com/track/([a-zA-Z0-9]+)",
            r"spotify:track:([a-zA-Z0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def is_supported_url(self, url: str) -> bool:
        """Check if URL is supported by this source."""
        spotify_patterns = [
            r"spotify\.com/track/",
            r"spotify:track:",
            r"open\.spotify\.com/track/",
        ]

        return any(re.search(pattern, url.lower()) for pattern in spotify_patterns)
