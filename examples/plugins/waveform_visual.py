"""
Waveform visual example for V4 Deluxe.
"""
from modpmv.plugins.base import VisualPlugin
from moviepy.editor import VideoClip, AudioFileClip
import numpy as np

class WaveformVisual(VisualPlugin):
    name = "waveform-visual"
    description = "Animated bar waveform visual"
    tags = ["waveform","audio-reactive"]
    version = "0.2"

    def render(self, audio_path, duration, size):
        sr = 8000
        mono = np.zeros(1)
        if audio_path:
            a = AudioFileClip(audio_path)
            arr = a.to_soundarray(fps=sr)
            mono = arr.mean(axis=1)
        N = max(128, min(2048, int(size[0]//2)))
        if len(mono) > 0:
            window = max(1, len(mono)//N)
            env = [abs(mono[i*window:(i+1)*window]).mean() for i in range(N)]
            maxenv = max(env) or 1.0
            env = [v/maxenv for v in env]
        else:
            env = [0]*N
        def make_frame(t):
            W,H = size
            img = np.zeros((H,W,3), dtype=np.uint8) + 8
            bar_w = max(1, W//N)
            for i,v in enumerate(env):
                h=int(v*(H*0.45))
                x=i*bar_w
                img[H//2-h:H//2+h, x:x+bar_w] = (30,200,255)
            return img
        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_fps(24)
        return clip.set_duration(duration)