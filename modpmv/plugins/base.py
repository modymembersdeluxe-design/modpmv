"""
Plugin base classes and helpers for ModPMV Deluxe.
Plugins should define metadata: name, description, tags, version, license, deps(optional)
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List
from pydub import AudioSegment

class PluginMeta:
    name: str = "unnamed"
    description: str = "No description"
    tags: List[str] = []
    version: str = "0.0.1"
    license: str = "MIT"
    deps: List[str] = []

class AudioPlugin(ABC, PluginMeta):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    @abstractmethod
    def process(self, audio: AudioSegment) -> AudioSegment:
        raise NotImplementedError
    def preview(self, audio: AudioSegment, preview_ms: int = 5000) -> AudioSegment:
        return self.process(audio)

class AudioEffectPlugin(AudioPlugin):
    pass

class VisualPlugin(ABC, PluginMeta):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    @abstractmethod
    def render(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        raise NotImplementedError
    def preview(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        return self.render(audio_path, min(duration,6.0), size)

class VisualEffectPlugin(VisualPlugin):
    @abstractmethod
    def apply(self, clip):
        raise NotImplementedError

class LayeredVisualPlugin(VisualPlugin):
    @abstractmethod
    def create_layers(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]) -> List[Dict[str, Any]]:
        raise NotImplementedError