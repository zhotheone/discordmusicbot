import re
from typing import Union


def validate_volume(volume: Union[int, float]) -> bool:
    """Validate volume level (0-100 for int, 0.0-1.0 for float)."""
    if isinstance(volume, int):
        return 0 <= volume <= 100
    elif isinstance(volume, float):
        return 0.0 <= volume <= 1.0
    return False


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))


def validate_filter_name(filter_name: str, available_filters: list) -> bool:
    """Validate filter name."""
    return filter_name in available_filters


def validate_repeat_mode(mode: str) -> bool:
    """Validate repeat mode."""
    return mode in ["off", "track", "queue"]


def sanitize_search_query(query: str, max_length: int = 200) -> str:
    """Sanitize and validate search query."""
    if not query or not isinstance(query, str):
        return ""
    
    # Remove excessive whitespace
    query = ' '.join(query.split())
    
    # Truncate if too long
    if len(query) > max_length:
        query = query[:max_length].rstrip()
    
    return query


def validate_user_id(user_id: Union[int, str]) -> bool:
    """Validate Discord user ID."""
    try:
        user_id = int(user_id)
        # Discord IDs are typically 17-19 digits (snowflakes)
        return 10**16 <= user_id <= 10**19
    except (ValueError, TypeError):
        return False


def validate_guild_id(guild_id: Union[int, str]) -> bool:
    """Validate Discord guild ID."""
    return validate_user_id(guild_id)  # Same validation as user IDs