"""
Fly-in/out plugin — animates a clip flying in, then flying out, using keyframe-like configuration.
"""
from modpmv.plugins.base import VisualPlugin, KeyframeGraph
from moviepy.editor import VideoFileClip, CompositeVideoClip

class FlyInOut(VisualPlugin):
    name = "fly-in-out"
    description = "Fly in, hold, then fly out animation"
    tags = ["animation","keyframe","3d-like"]

    def render(self, audio_path, duration, size):
        src = self.config.get("source_video")
        if src:
            base = VideoFileClip(src).subclip(0, min(duration, VideoFileClip(src).duration)).resize(newsize=size)
        else:
            from moviepy.video.VideoClip import ColorClip
            base = ColorClip(size=size, color=(40,40,80)).set_duration(duration)

        # keyframes for x position (left->center->right) expressed as graph
        kg = KeyframeGraph(self.config.get("x_keyframes", {0.0: -size[0], 0.2: size[0]*0.1, 0.8: size[0]*0.4, 1.0: size[0]}))
        def pos_fn(t):
            x = kg.value(t/duration) if isinstance(kg, KeyframeGraph) else 0
            return (x, int(size[1]*0.1))
        clip = base.set_pos(lambda t: pos_fn(t))
        return CompositeVideoClip([clip], size=size).set_duration(duration)