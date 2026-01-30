"""
Starter bump-map/displacement plugin.

This is a placeholder demonstrating how to wrap a per-frame numpy transform to simulate
a bump/displacement effect. For real bump mapping, implement normal-map sampling or use GPU.
"""
from modpmv.plugins.base import VisualEffectPlugin
import numpy as np

class BumpMap(VisualEffectPlugin):
    name = "bump-map"
    description = "Simulated bump/displacement map effect (placeholder)"
    tags = ["bump","displacement","effect"]

    def apply(self, clip):
        # naive per-frame displacement: blur and offset channels slightly by small amounts
        def fl(im):
            h, w, c = im.shape
            # small sinusoidal offset
            import math
            t = 0.0  # moviepy doesn't pass t here; in real use use fl_image with t-aware function
            shift_x = int((math.sin(t*2*math.pi) * 3))
            shift_y = int((math.cos(t*2*math.pi) * 3))
            out = np.roll(im, shift_x, axis=1)
            out = np.roll(out, shift_y, axis=0)
            return out
        return clip.fl_image(fl)