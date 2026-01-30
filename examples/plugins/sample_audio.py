"""
Simple AudioPlugin example.

This plugin normalizes audio and optionally reverses it.
"""
from modpmv.plugins.base import AudioPlugin
from pydub import AudioSegment

class SampleAudioPlugin(AudioPlugin):
    name = "sample-normalize-reverse"
    description = "Normalize audio and optionally reverse"

    def process(self, audio: AudioSegment) -> AudioSegment:
        # normalize
        out = audio.normalize()
        if self.config.get("reverse", False):
            out = out.reverse()
        return out