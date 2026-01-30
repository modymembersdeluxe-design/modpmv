"""
Simple audio processor plugin example: gain and optional reverse
"""
from modpmv.plugins.base import AudioEffectPlugin
from pydub import AudioSegment

class SimpleAudioEffect(AudioEffectPlugin):
    name = "simple-audio-processor"
    description = "Apply gain and optional reverse"
    tags = ["audio-effect","gain","reverse"]

    def process(self, audio: AudioSegment) -> AudioSegment:
        gain_db = float(self.config.get("gain_db", 0.0))
        out = audio + gain_db
        if self.config.get("reverse", False):
            out = out.reverse()
        return out