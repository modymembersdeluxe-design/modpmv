"""
Plugin interfaces (V3):
- AudioPlugin / AudioEffectPlugin
- VisualPlugin / VisualEffectPlugin / LayeredVisualPlugin
- Plugins must provide metadata: name, description, tags, version
- Plugins may implement preview(self, audio_path, duration, size) to speed GUI previews
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List
from pydub import AudioSegment

class PluginMeta:
    name: str = "unnamed"
    description: str = "No description"
    tags: List[str] = []
    version: str = "0.0.1"

class AudioPlugin(ABC, PluginMeta):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    @abstractmethod
    def process(self, audio: AudioSegment) -> AudioSegment:
        raise NotImplementedError
    def preview(self, audio: AudioSegment, preview_ms: int = 5000) -> AudioSegment:
        """Optional quick preview transform; default uses full process."""
        return self.process(audio)

class AudioEffectPlugin(AudioPlugin):
    pass

class VisualPlugin(ABC, PluginMeta):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    @abstractmethod
    def render(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        """Return a moviepy VideoClip"""
        raise NotImplementedError
    def preview(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        """Optional short preview clip (1-6s)."""
        return self.render(audio_path, min(duration, 6.0), size)

class VisualEffectPlugin(VisualPlugin):
    @abstractmethod
    def apply(self, clip):
        raise NotImplementedError

class LayeredVisualPlugin(VisualPlugin):
    @abstractmethod
    def create_layers(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]) -> List[Dict[str, Any]]:
        """
        Return list of layer dicts: { "clip": clip, "name": str, "z": int, "opacity": float, "blend": "normal" }
        """
        raise NotImplementedError