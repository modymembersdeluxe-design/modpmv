"""
Video renderer (starter) — build visuals synchronized to audio.
This uses moviepy to create a simple waveform + random image montage.
"""
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, CompositeVideoClip
import os
import random
from typing import List

def image_montage_from_folder(folder: str, duration: float, size=(1280,720)) -> ImageClip:
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".png",".jpg",".jpeg"))]
    if not files:
        # fallback: color clip
        from moviepy.video.VideoClip import ColorClip
        return ColorClip(size=size, color=(0,0,0)).set_duration(duration)
    chosen = random.choice(files)
    clip = ImageClip(chosen).resize(newsize=size).set_duration(duration)
    return clip

def render_video_for_audio(audio_path: str, image_folder: str, out_path: str, fps: int=24, size=(1280,720)):
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    # create sequence of image clips, each e.g. 2 seconds
    segment_dur = 2.0
    clips = []
    t = 0.0
    while t < duration:
        seg_dur = min(segment_dur, duration - t)
        imgclip = image_montage_from_folder(image_folder, seg_dur, size=size)
        clips.append(imgclip)
        t += seg_dur
    video = concatenate_videoclips(clips)
    video = video.set_audio(audio)
    video.write_videofile(out_path, fps=fps, audio_codec="aac")