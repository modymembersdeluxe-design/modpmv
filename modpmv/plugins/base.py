"""
Plugin base interfaces for ModPMV.

Define plugin APIs here so downstream plugins can subclass these.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from pydub import AudioSegment

class AudioPlugin(ABC):
    """
    Audio plugins must implement `process` which receives an AudioSegment and returns
    a new AudioSegment (processed) or None to skip.
    """
    name: str = "unnamed-audio-plugin"
    description: str = "No description"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def process(self, audio: AudioSegment) -> AudioSegment:
        """
        Transform or generate audio. Must return an AudioSegment.
        """
        raise NotImplementedError

class VisualPlugin(ABC):
    """
    Visual plugins must implement `render` which receives:
      - audio_path: path to the audio file (may be None)
      - duration: float seconds
      - size: (w, h) tuple
      - config: plugin-specific config dict
    Must return a moviepy clip (VideoClip / ImageClip) or raise on error.
    """
    name: str = "unnamed-visual-plugin"
    description: str = "No description"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def render(self, audio_path: Optional[str], duration: float, size: Tuple[int, int]):
        """
        Return a moviepy VideoClip (or similar) for the provided audio/duration/size.
        """
        raise NotImplementedError