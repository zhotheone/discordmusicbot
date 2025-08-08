import asyncio
import logging
from typing import List, Optional, Dict, Any
import re

import yt_dlp
from domain.entities.track import Track, TrackSource
from domain.interfaces.audio_source import AudioSource

logger = logging.getLogger(__name__)


class YouTubeSource(AudioSource):
    """YouTube audio source implementation."""
    
    def __init__(self):
        self.ytdl_options = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
        }
        
        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_options)
    
    async def search(self, query: str, max_results: int = 5) -> List[Track]:
        """Search for tracks on YouTube."""
        try:
            # Run blocking operation in thread pool
            loop = asyncio.get_event_loop()
            search_results = await loop.run_in_executor(
                None,
                self._search_sync,
                query,
                max_results
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
            info = await loop.run_in_executor(
                None,
                self._extract_info_sync,
                url
            )
            
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
            info = await loop.run_in_executor(
                None,
                self._extract_info_sync,
                track.url
            )
            
            if not info:
                return None
            
            # Get the best audio format URL
            formats = info.get('formats', [])
            for fmt in formats:
                if fmt.get('acodec') != 'none' and fmt.get('url'):
                    return fmt['url']
            
            # Fallback to direct URL
            return info.get('url')
            
        except Exception as e:
            logger.error(f"Error getting stream URL for track '{track.title}': {e}")
            return None
    
    def _search_sync(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Synchronous search operation."""
        try:
            # Use ytsearch to search YouTube
            search_query = f"ytsearch{max_results}:{query}"
            
            with yt_dlp.YoutubeDL(self.ytdl_options) as ytdl:
                search_results = ytdl.extract_info(
                    search_query,
                    download=False
                )
            
            if 'entries' in search_results:
                return search_results['entries']
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
        self,
        entry: Dict[str, Any],
        requester_id: int = 0
    ) -> Optional[Track]:
        """Create a Track object from YouTube entry."""
        try:
            if not entry:
                return None
            
            title = entry.get('title', 'Unknown Title')
            url = entry.get('webpage_url') or entry.get('url', '')
            duration = entry.get('duration', 0)
            thumbnail_url = self._get_best_thumbnail(entry.get('thumbnails', []))
            
            # Extract artist from title or uploader
            artist = self._extract_artist(title) or entry.get('uploader', 'Unknown Artist')
            
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
                track_id=entry.get('id'),
                metadata={
                    'view_count': entry.get('view_count'),
                    'upload_date': entry.get('upload_date'),
                    'uploader': entry.get('uploader'),
                    'like_count': entry.get('like_count')
                }
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
            key=lambda x: (x.get('width', 0) * x.get('height', 0)),
            reverse=True
        )
        
        return sorted_thumbnails[0].get('url')
    
    def _extract_artist(self, title: str) -> Optional[str]:
        """Extract artist name from title using common patterns."""
        patterns = [
            r'^([^-]+)\s*-\s*(.+)$',  # "Artist - Song"
            r'^([^|]+)\s*\|\s*(.+)$',  # "Artist | Song"
            r'^([^:]+):\s*(.+)$',      # "Artist: Song"
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
            'youtube.com',
            'youtu.be',
            'm.youtube.com',
            'www.youtube.com'
        ]
        
        return any(domain in url.lower() for domain in youtube_domains)