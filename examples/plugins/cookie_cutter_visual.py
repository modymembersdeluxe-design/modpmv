"""
Cookie Cutter plugin — masks input with a shape (circle, star, rect).
Works as a VisualEffectPlugin that returns a clip masked by the shape.
"""
from modpmv.plugins.base import VisualEffectPlugin
from moviepy.editor import VideoFileClip, ColorClip
import numpy as np

class CookieCutter(VisualEffectPlugin):
    name = "cookie-cutter"
    description = "Apply shape mask (circle/rect) to a clip"
    tags = ["mask","cookie-cutter","shape"]

    def apply(self, clip):
        size = clip.size
        shape = self.config.get("shape", "circle")
        def make_mask_frame(t, w=size[0], h=size[1]):
            import math
            frame = np.zeros((h, w), dtype=np.uint8)
            cx = int(w/2 + self.config.get("offset_x", 0))
            cy = int(h/2 + self.config.get("offset_y", 0))
            if shape == "circle":
                r = int(min(w,h) * 0.35 * self.config.get("scale", 1.0))
                ys, xs = np.ogrid[:h, :w]
                mask = (xs - cx)**2 + (ys - cy)**2 <= r*r
                frame[mask] = 255
            else:
                # rect fallback
                rw = int(w * 0.6 * self.config.get("scale", 1.0))
                rh = int(h * 0.6 * self.config.get("scale", 1.0))
                x0 = max(0, cx - rw//2)
                y0 = max(0, cy - rh//2)
                frame[y0:y0+rh, x0:x0+rw] = 255
            return np.expand_dims(frame, axis=2)
        mask = clip.fl(lambda gf, t: make_mask_frame(t), apply_to=['mask'])
        # set mask to clip
        clip = clip.set_mask(mask)
        return clip