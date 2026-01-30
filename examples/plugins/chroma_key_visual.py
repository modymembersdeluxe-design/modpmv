"""
Simple Chroma Key Visual Plugin (example).

This plugin will take a foreground video clip (or the provided audio if used as source)
and remove a green-screen-like color, compositing it over a fallback background.
This is a simple per-frame chroma key using numpy; replace with a more robust algorithm
for production (tolerance / smoothing / spill suppression).
"""
from modpmv.plugins.base import VisualPlugin
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, ImageClip
import numpy as np

class ChromaKeyVisual(VisualPlugin):
    name = "chroma-key-visual"
    description = "Simple chroma-key compositor (green key)"
    tags = ["chroma","composite","layer"]

    def render(self, audio_path, duration, size):
        # config keys: source_video (optional), bg_color, key_color, threshold
        src = self.config.get("source_video")
        key_color = tuple(self.config.get("key_color", (0, 255, 0)))
        threshold = float(self.config.get("threshold", 80.0))
        bg_color = tuple(self.config.get("bg_color", (10, 10, 10)))

        # load source or fallback to color
        if src:
            clip = VideoFileClip(src).subclip(0, min(duration, VideoFileClip(src).duration))
            clip = clip.resize(newsize=size)
        else:
            clip = ColorClip(size=size, color=(0,255,0)).set_duration(duration)

        # create mask clip by comparing distance to key_color
        def mask_frame(img):
            # img is (H,W,3)
            diff = np.linalg.norm(img.astype(np.float32) - np.array(key_color, dtype=np.float32), axis=2)
            mask = (diff > threshold).astype(np.uint8) * 255  # foreground where distance > threshold
            # return single-channel alpha
            return mask

        # moviepy expects mask clip to be a video clip with grayscale frames (0-255)
        mask_clip = clip.fl_image(lambda im: np.expand_dims(mask_frame(im), axis=2)).set_duration(clip.duration)
        mask_clip = mask_clip.set_fps(clip.fps)

        # build background
        bg = ColorClip(size=size, color=bg_color).set_duration(clip.duration)

        # set mask on clip and composite
        clip = clip.set_mask(mask_clip)
        comp = CompositeVideoClip([bg, clip]).set_duration(clip.duration)
        return comp.set_duration(duration)