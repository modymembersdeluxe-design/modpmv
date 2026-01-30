"""
Plugin base types and helpers (V2): AudioPlugin, AudioEffectPlugin, VisualPlugin,
VisualEffectPlugin, LayeredVisualPlugin and KeyframeGraph for simple interpolation.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List
from pydub import AudioSegment
import bisect

class KeyframeGraph:
    def __init__(self, keys: Optional[Dict[float, float]] = None):
        self.times = []
        self.values = []
        if keys:
            for t, v in sorted(keys.items()):
                self.times.append(float(t))
                self.values.append(float(v))

    def value(self, t: float) -> float:
        if not self.times:
            return 0.0
        if t <= self.times[0]:
            return self.values[0]
        if t >= self.times[-1]:
            return self.values[-1]
        i = bisect.bisect_right(self.times, t) - 1
        t0, t1 = self.times[i], self.times[i+1]
        v0, v1 = self.values[i], self.values[i+1]
        if t1 == t0:
            return v0
        alpha = (t - t0) / (t1 - t0)
        return v0 + (v1 - v0) * alpha

class AudioPlugin(ABC):
    name: str = "unnamed-audio-plugin"
    description: str = "No description"
    tags: List[str] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def process(self, audio: AudioSegment) -> AudioSegment:
        raise NotImplementedError

class AudioEffectPlugin(AudioPlugin):
    pass

class VisualPlugin(ABC):
    name: str = "unnamed-visual-plugin"
    description: str = "No description"
    tags: List[str] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def render(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        raise NotImplementedError

class VisualEffectPlugin(VisualPlugin):
    @abstractmethod
    def apply(self, clip):
        raise NotImplementedError

class LayeredVisualPlugin(VisualPlugin):
    @abstractmethod
    def create_layers(self, audio_path: Optional[str], duration: float, size: Tuple[int,int]):
        """
        Return list of layer dicts: { "clip": clip, "name": str, "z": int, "opacity": float }
        """
        raise NotImplementedError