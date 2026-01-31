"""
Beat-slicer audio plugin example.
"""
from modpmv.plugins.base import AudioEffectPlugin
from pydub import AudioSegment
import numpy as np
import librosa
import random

class BeatSlicer(AudioEffectPlugin):
    name = "beat-slicer"
    description = "Beat-slice and optionally shuffle"
    tags = ["audio-effect","beat"]
    version = "0.2"

    def process(self, audio: AudioSegment) -> AudioSegment:
        sr = int(self.config.get("sr", 22050))
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        if audio.channels > 1:
            samples = samples.reshape((-1, audio.channels)).mean(axis=1)
        y = samples / (np.max(np.abs(samples)) or 1.0)
        try:
            _, beats = librosa.beat.beat_track(y=y, sr=sr)
            times = librosa.frames_to_time(beats, sr=sr)
        except Exception:
            return audio
        segs=[]
        for i in range(len(times)-1):
            s=int(times[i]*1000); e=int(times[i+1]*1000)
            segs.append(audio[s:e])
        if self.config.get("shuffle", True):
            random.seed(self.config.get("seed",0))
            random.shuffle(segs)
        if segs:
            out = segs[0]
            for s in segs[1:]:
                out = out.append(s, crossfade=0)
            return out
        return audio