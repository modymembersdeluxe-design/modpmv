"""
Blinds-style transition plugin (3D-like illusion) — splits clip into vertical blinds
and animates them in with staggered timing.

This is a VisualEffectPlugin applied to a source clip or returned as a full clip.
"""
from modpmv.plugins.base import VisualPlugin
from moviepy.editor import VideoFileClip, CompositeVideoClip
import math

class Blinds3D(VisualPlugin):
    name = "3d-blinds"
    description = "3D-style blinds transition (vertical slices with staggered translate/rotate)"
    tags = ["transition","3d","blinds"]

    def render(self, audio_path, duration, size):
        # config: source_video (optional), slices, duration, angle, depth
        src = self.config.get("source_video")
        slices = int(self.config.get("slices", 10))
        ang = float(self.config.get("angle", 15.0))
        depth = float(self.config.get("depth", 100.0))

        if src:
            base = VideoFileClip(src).subclip(0, min(duration, VideoFileClip(src).duration)).resize(newsize=size)
        else:
            from moviepy.video.VideoClip import ColorClip
            base = ColorClip(size=size, color=(20,20,20)).set_duration(duration)

        w, h = size
        slice_w = w / slices
        clips = []
        for i in range(slices):
            x0 = int(i*slice_w)
            x1 = int(min(w, (i+1)*slice_w))
            sub = base.crop(x1=x1, x0=x0).set_duration(duration)
            # animate x-position and rotation with lambda
            delay = (i / slices) * 0.6  # stagger
            def pos_fn(t, i=i, delay=delay, slice_w=slice_w):
                if t < delay:
                    return (x0, 0)
                tt = (t - delay) / max(1e-6, (duration - delay))
                # fly from slightly above and rotated
                x = x0 + (math.sin(tt*math.pi) * (ang/100.0) * slice_w)
                y = (1-tt) * (-depth)
                return (x, y)
            sub = sub.set_pos(pos_fn)
            clips.append(sub)
        comp = CompositeVideoClip(clips, size=size).set_duration(duration)
        return comp