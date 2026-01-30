"""
Video renderer (V2) — map module events to video samples/images and support visual plugins.
"""
from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip, ColorClip, concatenate_videoclips, CompositeVideoClip
from typing import List, Optional, Tuple
import os, random
from modpmv.mod_parser import Module
from modpmv.assets import find_video_for_sample, list_assets

DEFAULT_ROW_SECONDS = 0.25
DEFAULT_SIZE = (1280,720)

def _image_clip_for_row(image_folders: List[str], duration: float, size: Tuple[int,int]):
    images = []
    for folder in image_folders:
        images += list_assets(folder, exts=(".png", ".jpg", ".jpeg", ".bmp"))
    if images:
        chosen = random.choice(images)
        return ImageClip(chosen).resize(newsize=size).set_duration(duration)
    return ColorClip(size=size, color=(10,10,10)).set_duration(duration)

def render_video_from_module(module: Module,
                             audio_path: str,
                             video_asset_folders: List[str],
                             image_asset_folders: List[str],
                             out_path: str,
                             fps: int = 24,
                             size: Tuple[int,int] = DEFAULT_SIZE,
                             row_seconds: float = DEFAULT_ROW_SECONDS,
                             visual_plugins: Optional[List] = None) -> str:
    audio = AudioFileClip(audio_path)
    total = audio.duration
    clips = []
    t = 0.0
    used_video_files = []
    for idx in (module.order or list(range(len(module.patterns)))):
        if idx < 0 or idx >= len(module.patterns):
            continue
        patt = module.patterns[idx]
        for row in patt.rows:
            if t >= total:
                break
            seg_dur = min(row_seconds, total - t)
            chosen_sample = None
            for tok in row:
                if tok.upper().startswith("SAMPLE:"):
                    chosen_sample = tok.split(":",1)[1]
                    break
            clip = None
            if chosen_sample:
                vf = find_video_for_sample(chosen_sample, video_asset_folders)
                if vf and os.path.exists(vf):
                    try:
                        v = VideoFileClip(vf)
                        if v.duration > seg_dur:
                            v = v.subclip(0, seg_dur)
                        else:
                            if v.duration > 0:
                                repeats = int(seg_dur // v.duration)
                                parts = [v] * repeats
                                rem = seg_dur - repeats*v.duration
                                if rem > 0:
                                    parts.append(v.subclip(0, rem))
                                v = concatenate_videoclips(parts)
                            else:
                                v = v.set_duration(seg_dur)
                        clip = v.resize(newsize=size).set_duration(seg_dur)
                        used_video_files.append(vf)
                    except Exception:
                        clip = None
            if clip is None:
                clip = _image_clip_for_row(image_asset_folders, seg_dur, size)
            # apply visual plugins that can modify/compose the row clip
            if visual_plugins:
                for vp in visual_plugins:
                    try:
                        # visual plugin may be VisualEffectPlugin with apply or full VisualPlugin.render
                        if hasattr(vp, "apply"):
                            clip = vp.apply(clip)
                        elif hasattr(vp, "render"):
                            # render may return full comp — skip for per-row simple pipeline
                            candidate = vp.render(audio_path, seg_dur, size)
                            if candidate:
                                clip = candidate
                    except Exception:
                        continue
            clips.append(clip)
            t += seg_dur
        if t >= total:
            break

    if not clips:
        clips = [ColorClip(size=size, color=(0,0,0)).set_duration(total)]

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    video.write_videofile(out_path, fps=fps, audio_codec="aac")
    # close
    try:
        video.close()
    except Exception:
        pass
    try:
        audio.close()
    except Exception:
        pass
    return out_path