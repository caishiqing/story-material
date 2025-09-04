"""
Audio utility functions for parsing audio files and extracting metadata
"""

import os
from loguru import logger
from typing import Optional
from pathlib import Path


def get_audio_duration(file_path: str) -> Optional[int]:
    """
    Get audio file duration in seconds

    Args:
        file_path: Path to the audio file

    Returns:
        Duration in seconds (rounded) or None if unable to parse
    """
    # Using global loguru logger

    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("pydub is required for audio parsing. Install with: pip install pydub")
        return None

    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning(f"Audio file not found: {file_path}")
            return None

        # Load audio file and get duration
        audio = AudioSegment.from_file(file_path)
        duration_ms = len(audio)
        duration_seconds = round(duration_ms / 1000)

        logger.debug(f"Parsed audio duration: {file_path} -> {duration_seconds}s")
        return duration_seconds

    except Exception as e:
        logger.error(f"Failed to parse audio file {file_path}: {str(e)}")
        return None


def validate_audio_file(file_path: str) -> bool:
    """
    Validate if the file is a valid audio file

    Args:
        file_path: Path to the audio file

    Returns:
        True if valid audio file, False otherwise
    """
    # Using global loguru logger

    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("pydub is required for audio validation")
        return False

    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return False

        # Try to load the audio file
        AudioSegment.from_file(file_path)
        return True

    except Exception as e:
        logger.debug(f"Invalid audio file {file_path}: {str(e)}")
        return False


def get_audio_info(file_path: str) -> dict:
    """
    Get comprehensive audio file information

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary with audio information
    """
    # Using global loguru logger

    info = {
        "path": file_path,
        "exists": os.path.exists(file_path),
        "size": None,
        "duration": None,
        "format": None,
        "channels": None,
        "sample_rate": None,
        "valid": False
    }

    if not info["exists"]:
        return info

    try:
        # Get file size
        info["size"] = os.path.getsize(file_path)

        # Get file extension
        info["format"] = Path(file_path).suffix.lower()

        # Try to get audio metadata
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(file_path)

            info["duration"] = round(len(audio) / 1000)  # Convert to seconds
            info["channels"] = audio.channels
            info["sample_rate"] = audio.frame_rate
            info["valid"] = True

        except ImportError:
            logger.warning("pydub not available for detailed audio analysis")
        except Exception as e:
            logger.debug(f"Could not parse audio metadata: {str(e)}")

    except Exception as e:
        logger.error(f"Error getting audio info for {file_path}: {str(e)}")

    return info


def suggest_audio_type_from_path(file_path: str) -> Optional[str]:
    """
    Suggest audio type based on file path patterns

    Args:
        file_path: Path to the audio file

    Returns:
        Suggested audio type or None
    """
    path_lower = file_path.lower()

    # Common path patterns for audio types
    type_patterns = {
        "环境音效": ["环境", "ambient", "environment"],
        "天气音效": ["雷", "雨", "rain", "thunder", "storm", "weather", "wind"],
        "城市环境": ["城市", "city", "urban", "traffic", "street"],
        "交通工具": ["车", "飞机", "火车", "直升机", "helicopter", "car", "train", "plane"],
        "转场音效": ["转场", "transition", "hit", "撞击", "whoosh"],
        "自然音效": ["自然", "nature", "forest", "ocean", "bird", "water"],
        "人声音效": ["人声", "voice", "crowd", "talk", "speech"],
        "音乐": ["音乐", "music", "bgm", "background"]
    }

    for audio_type, patterns in type_patterns.items():
        for pattern in patterns:
            if pattern in path_lower:
                return audio_type

    return None
