"""
Simple VisualPlugin example.

Produces a solid-color clip for the whole duration. Replace with frame-based
drawing, waveform visualization, or other effects.
"""
from modpmv.plugins.base import VisualPlugin
from moviepy.video.VideoClip import ColorClip

class SampleVisualPlugin(VisualPlugin):
    name = "sample-solid-visual"
    description = "Solid-color visual plugin (demo)"

    def render(self, audio_path, duration, size):
        color = tuple(self.config.get("color", (30, 30, 120)))
        clip = ColorClip(size, color=color).set_duration(duration)
        return clip