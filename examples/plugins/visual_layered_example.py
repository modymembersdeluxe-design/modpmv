"""
Layered visual plugin: demonstrates composing multiple layers with blending & keyframe control.
"""
from modpmv.plugins.base import LayeredVisualPlugin, KeyframeGraph
from moviepy.editor import ColorClip, ImageClip, CompositeVideoClip

class LayeredExample(LayeredVisualPlugin):
    name = "layered-sample"
    description = "Compose background + image layer + overlay text/shape"
    tags = ["layer","composite","example"]

    def create_layers(self, audio_path, duration, size):
        layers = []
        # background
        bg = ColorClip(size=size, color=tuple(self.config.get("bg_color", (12,12,60)))).set_duration(duration)
        layers.append({"clip": bg, "name": "bg", "z": 0, "opacity": 1.0})
        # optional image
        img = self.config.get("image")
        if img:
            ic = ImageClip(img).resize(width=int(size[0]*0.6)).set_duration(duration)
            layers.append({"clip": ic.set_pos(("center","center")), "name": "image", "z": 1, "opacity": 1.0})
        # overlay color bar that pulsed using keyframe
        kg = KeyframeGraph(self.config.get("pulse_keys", {0.0:0.2, 0.5:1.0, 1.0:0.2}))
        # create overlay clip that modifies opacity via lambda
        overlay = ColorClip(size=(size[0], int(size[1]*0.12)), color=(255,255,255)).set_duration(duration)
        overlay = overlay.set_opacity(lambda t: kg.value(t/duration))
        layers.append({"clip": overlay.set_pos(("center", size[1]-int(size[1]*0.12))), "name": "overlay", "z": 2, "opacity": 1.0})
        return layers

    def render(self, audio_path, duration, size):
        layers = self.create_layers(audio_path, duration, size)
        # sort by z
        layers = sorted(layers, key=lambda l: l.get("z", 0))
        clips = [l["clip"].set_opacity(l.get("opacity",1.0)) for l in layers]
        comp = CompositeVideoClip(clips, size=size).set_duration(duration)
        return comp