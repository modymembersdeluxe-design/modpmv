"""
Audio renderer (starter) — assemble/generate audio clips.
Uses pydub for simple concatenation/exports.
For advanced DSP, integrate librosa/numpy and provide more complex sample processing.
"""
from pydub import AudioSegment
import random
import os
from typing import List

def load_sample(path: str) -> AudioSegment:
    return AudioSegment.from_file(path)

def random_clip_from_folder(folder: str, length_ms: int = 2000) -> AudioSegment:
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".wav",".mp3",".ogg"))]
    if not files:
        raise FileNotFoundError("No audio files in folder")
    chosen = random.choice(files)
    seg = load_sample(chosen)
    if len(seg) > length_ms:
        start = random.randint(0, len(seg)-length_ms)
        seg = seg[start:start+length_ms]
    return seg

def assemble_track(clips: List[AudioSegment], crossfade_ms: int = 50) -> AudioSegment:
    if not clips:
        return AudioSegment.silent(duration=1000)
    out = clips[0]
    for clip in clips[1:]:
        out = out.append(clip, crossfade=crossfade_ms)
    return out

def export_track(out: AudioSegment, path: str, format: str = "mp3", bitrate="192k"):
    out.export(path, format=format, bitrate=bitrate)