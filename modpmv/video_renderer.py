import os
import random
from typing import List, Optional, Tuple, Dict, Any
from moviepy.editor import (AudioFileClip, VideoFileClip, ImageClip, ColorClip,
                            concatenate_videoclips, CompositeVideoClip)
from .assets import find_video_for_sample, list_assets
from .utils import ensure_dir

# Import audio renderer helpers for preview audio generation
from .audio_renderer import render_audio_from_module_data, export_audio_segment

DEFAULT_ROW_SECONDS = 0.25
DEFAULT_SIZE = (1280, 720)

def _image_clip_for_row(image_folders: List[str], duration: float, size: Tuple[int,int]):
    images = []
    for folder in image_folders:
        images += list_assets(folder, exts=(".png", ".jpg", ".jpeg", ".bmp"))
    if images:
        chosen = random.choice(images)
        return ImageClip(chosen).resize(newsize=size).set_duration(duration)
    return ColorClip(size=size, color=(10,10,10)).set_duration(duration)

def _write_video_moviepy(clips, audio, out_path: str, fps:int=24):
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    ensure_dir(os.path.dirname(out_path) or ".")
    video.write_videofile(out_path, fps=fps, audio_codec="aac")
    try:
        video.close()
    except Exception:
        pass

def render_video_from_module_data(module_data: Dict[str, Any],
                                  audio_path: str,
                                  video_asset_folders: List[str],
                                  image_asset_folders: List[str],
                                  out_path: str,
                                  fps: int = 24,
                                  size: Tuple[int,int] = DEFAULT_SIZE,
                                  row_seconds: float = DEFAULT_ROW_SECONDS,
                                  visual_plugins: Optional[List] = None,
                                  mode: str = "moviepy") -> Tuple[str, List[str]]:
    """
    Render a full video for module_data. Returns (out_path, used_video_files).
    Mode can be "moviepy" (default) or "ffmpeg" (stub uses moviepy).
    """
    audio = AudioFileClip(audio_path)
    total = audio.duration
    clips = []
    used_video_files = []
    channels = int(module_data.get("channels", 32))
    patterns = module_data.get("patterns", [])
    order = module_data.get("order", list(range(len(patterns))))
    t = 0.0

    for patt_idx in order:
        if patt_idx < 0 or patt_idx >= len(patterns):
            continue
        pattern = patterns[patt_idx]
        for row in pattern:
            if t >= total:
                break
            seg_dur = min(row_seconds, total - t)
            per_channel_clips = []
            for ch_index in range(channels):
                token = "REST"
                try:
                    token = row[ch_index]
                except Exception:
                    token = "REST"
                chosen_sample = None
                if isinstance(token, str) and token.upper().startswith("SAMPLE:"):
                    chosen_sample = token.split(":",1)[1]
                channel_clip = None
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
                            channel_clip = v.resize(newsize=size).set_duration(seg_dur)
                            used_video_files.append(vf)
                        except Exception:
                            channel_clip = None
                if channel_clip is None:
                    channel_clip = _image_clip_for_row(image_asset_folders, seg_dur, size)
                    tint = ((ch_index * 37) % 255, (ch_index * 59) % 255, (ch_index * 83) % 255)
                    bar = ColorClip(size=(int(size[0]*0.15), int(size[1]*0.07)), color=tint).set_duration(seg_dur)
                    pos_x = int((ch_index % 8) * (size[0] * 0.02))
                    pos_y = int((ch_index // 8) * (size[1] * 0.06))
                    bar = bar.set_pos((pos_x, pos_y))
                    channel_clip = CompositeVideoClip([channel_clip, bar], size=size).set_duration(seg_dur)
                def pos_fn_factory(ch_i):
                    def pos_fn(t):
                        x = int((ch_i % 8) * (size[0] * 0.11))
                        y = int((ch_i // 8) * (size[1] * 0.12))
                        return (x, y)
                    return pos_fn
                channel_clip = channel_clip.set_pos(pos_fn_factory(ch_index))
                channel_clip = channel_clip.set_opacity(0.9 - min(0.6, ch_index * 0.01))
                per_channel_clips.append((ch_index, channel_clip))
            comp_clips = [c for _, c in sorted(per_channel_clips, key=lambda x: x[0])]
            row_comp = CompositeVideoClip(comp_clips, size=size).set_duration(seg_dur)
            if visual_plugins:
                for vp in visual_plugins:
                    try:
                        if hasattr(vp, "apply"):
                            row_comp = vp.apply(row_comp)
                        elif hasattr(vp, "render"):
                            candidate = vp.render(audio_path, seg_dur, size)
                            if candidate:
                                row_comp = candidate.set_duration(seg_dur)
                    except Exception:
                        continue
            clips.append(row_comp)
            t += seg_dur
        if t >= total:
            break

    if not clips:
        clips = [ColorClip(size=size, color=(0,0,0)).set_duration(total)]

    if mode == "moviepy":
        _write_video_moviepy(clips, audio, out_path, fps=fps)
    else:
        _write_video_moviepy(clips, audio, out_path, fps=fps)

    try:
        audio.close()
    except Exception:
        pass

    # return unique used files preserving order
    seen = []
    unique_used = []
    for f in used_video_files:
        if f not in seen:
            seen.append(f)
            unique_used.append(f)
    return out_path, unique_used

def render_preview(module_path: str,
                   audio_asset_folders: List[str],
                   video_asset_folders: List[str],
                   image_asset_folders: List[str],
                   preview_seconds: float = 6.0,
                   out_path: str = "output/preview.mp4",
                   size: Tuple[int,int] = (640,360),
                   visual_plugins: Optional[List] = None) -> str:
    """
    Parse module_path, render a short low-res preview of preview_seconds,
    write to out_path and attempt to open it (Windows: os.startfile).
    """
    # lazy import parse to avoid top-level dependency ordering issues
    from .mod_parser import parse
    # parse module (text or binary if openmpt adapter available)
    module_data = parse(module_path)
    # render audio for the module, then trim/pad to preview_seconds
    audio_seg = render_audio_from_module_data(module_data, audio_asset_folders, row_duration_ms=int(1000 * DEFAULT_ROW_SECONDS))
    preview_ms = int(preview_seconds * 1000)
    if len(audio_seg) > preview_ms:
        audio_seg = audio_seg[:preview_ms]
    elif len(audio_seg) < preview_ms:
        # pad by repeating content if too short
        needed = preview_ms - len(audio_seg)
        if len(audio_seg) > 0:
            audio_seg = audio_seg + audio_seg[:needed]
        else:
            from pydub import AudioSegment
            audio_seg = AudioSegment.silent(duration=preview_ms)
    ensure_dir(os.path.dirname(out_path) or ".")
    preview_audio_path = out_path.replace(".mp4", ".mp3")
    export_audio_segment(audio_seg, preview_audio_path)
    # Use the same module_data to render the preview video (moviepy composition)
    # For speed we keep the same module_data but row_seconds equals DEFAULT_ROW_SECONDS
    preview_out, used = render_video_from_module_data(module_data, preview_audio_path, video_asset_folders, image_asset_folders, out_path, fps=24, size=size, row_seconds=DEFAULT_ROW_SECONDS, visual_plugins=visual_plugins, mode="moviepy")
    # attempt to open preview in OS default player
    try:
        if os.name == "nt":
            os.startfile(preview_out)
        else:
            import subprocess, shutil
            opener = shutil.which("xdg-open") or shutil.which("open")
            if opener:
                subprocess.Popen([opener, preview_out])
    except Exception:
        pass
    return preview_out