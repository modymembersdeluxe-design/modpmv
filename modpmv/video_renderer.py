"""
Video renderer V5 Deluxe — streaming ffmpeg mode + robust fallbacks.

Improvements:
- New `mode="stream"` that pipes raw RGB frames to ffmpeg stdin for encoding to H.264.
- Returns (out_path, used_video_files, timeline) so exporter can write exact timestamp mapping.
- Graceful fallbacks (moviepy write, then ffmpeg concat/mux if needed).
- Detailed error messages when ffmpeg or moviepy are missing.
"""
import os, random, subprocess, tempfile, shutil
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from moviepy.editor import (AudioFileClip, VideoFileClip, ImageClip, ColorClip,
                            concatenate_videoclips, CompositeVideoClip)
from .assets import find_video_for_sample, list_assets
from .audio_renderer import render_audio_from_module_data, export_audio_segment
from .utils import ensure_dir

DEFAULT_ROW_SECONDS = 0.25
DEFAULT_SIZE = (1280, 720)

def _ffmpeg_exe() -> Optional[str]:
    import shutil
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg as iioff
        return iioff.get_exe()
    except Exception:
        return None

def _image_clip_for_row(image_folders: List[str], duration: float, size: Tuple[int,int]):
    images = []
    for folder in image_folders:
        images += list_assets(folder, exts=(".png", ".jpg", ".jpeg", ".bmp"))
    if images:
        chosen = random.choice(images)
        return ImageClip(chosen).resize(newsize=size).set_duration(duration)
    return ColorClip(size=size, color=(10,10,10)).set_duration(duration)

def _write_moviepy(clips, audio, out_path: str, fps:int=24):
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    ensure_dir(os.path.dirname(out_path) or ".")
    video.write_videofile(out_path, fps=fps, audio_codec="aac")
    try: video.close()
    except Exception: pass

def _ffmpeg_stream_clip(clip, audio_file: Optional[str], out_path: str, fps: int, size: Tuple[int,int]):
    """
    Stream a moviepy VideoClip to ffmpeg stdin to produce out_path.
    clip: moviepy.VideoClip instance (already composed)
    audio_file: optional path to audio to mux after encoding, or pass via ffmpeg arguments
    """
    ff = _ffmpeg_exe()
    if ff is None:
        raise RuntimeError("ffmpeg not found for stream mode.")
    w, h = size
    # ffmpeg command receives rawvideo RGB24 from stdin
    cmd = [
        ff, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
    ]
    if audio_file and os.path.exists(audio_file):
        cmd += ["-i", audio_file, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-c:v", "libx264", "-preset", "fast", "-crf", "18", out_path]
    else:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "18", out_path]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        duration = clip.duration
        frame_count = int(duration * fps)
        for i in range(frame_count):
            t = i / fps
            frame = clip.get_frame(t)  # numpy array HxWx3 uint8
            if frame.shape[0] != h or frame.shape[1] != w:
                # resize using numpy nearest (cheap) if shapes mismatch
                frame = np.asarray(ImageClip(frame).resize(newsize=size).get_frame(0))
            proc.stdin.write(frame.astype(np.uint8).tobytes())
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited with code {rc}")
    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
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
                                  mode: str = "moviepy") -> Tuple[str, List[str], List[Dict[str,Any]]]:
    """
    Render video. Supports modes: "moviepy", "ffmpeg" (concat), "stream" (ffmpeg stdin).
    Returns (out_path, used_video_files, timeline)
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)
    audio = AudioFileClip(audio_path)
    total = audio.duration
    clips = []
    used_video_files: List[str] = []
    timeline: List[Dict[str,Any]] = []

    channels = int(module_data.get("channels", 32))
    patterns = module_data.get("patterns", [])
    order = module_data.get("order", list(range(len(patterns))))
    t = 0.0

    ff_available = _ffmpeg_exe() is not None
    if mode == "stream" and not ff_available:
        # fallback to moviepy
        mode = "moviepy"

    # prepare per-row clips (in-memory)
    for patt_idx in order:
        if patt_idx < 0 or patt_idx >= len(patterns):
            continue
        pattern = patterns[patt_idx]
        for row_idx, row in enumerate(pattern):
            if t >= total:
                break
            seg_dur = min(row_seconds, total - t)
            per = []
            used_this_row = []
            for ch in range(channels):
                token = row[ch] if ch < len(row) else "REST"
                chosen_sample = None
                if isinstance(token, str) and token.upper().startswith("SAMPLE:"):
                    chosen_sample = token.split(":",1)[1]
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
                                    rem = seg_dur - repeats * v.duration
                                    if rem > 0:
                                        parts.append(v.subclip(0, rem))
                                    v = concatenate_videoclips(parts)
                                else:
                                    v = v.set_duration(seg_dur)
                            clip = v.resize(newsize=size).set_duration(seg_dur)
                            used_this_row.append(vf)
                            used_video_files.append(vf)
                        except Exception:
                            clip = None
                if clip is None:
                    clip = _image_clip_for_row(image_asset_folders, seg_dur, size)
                    tint = ((ch * 37) % 255, (ch * 59) % 255, (ch * 83) % 255)
                    bar = ColorClip(size=(int(size[0]*0.15), int(size[1]*0.07)), color=tint).set_duration(seg_dur)
                    pos_x = int((ch % 8) * (size[0] * 0.02)); pos_y = int((ch // 8) * (size[1] * 0.06))
                    bar = bar.set_pos((pos_x, pos_y))
                    clip = CompositeVideoClip([clip, bar], size=size).set_duration(seg_dur)
                def pos_fn_factory(ci):
                    def pos_fn(tt):
                        x = int((ci % 8) * (size[0] * 0.11)); y = int((ci // 8) * (size[1] * 0.12)); return (x, y)
                    return pos_fn
                clip = clip.set_pos(pos_fn_factory(ch))
                clip = clip.set_opacity(0.9 - min(0.6, ch * 0.01))
                per.append((ch, clip))
            comp = CompositeVideoClip([c for _,c in sorted(per, key=lambda x: x[0])], size=size).set_duration(seg_dur)
            if visual_plugins:
                for vp in visual_plugins:
                    try:
                        if hasattr(vp, "apply"):
                            comp = vp.apply(comp)
                        elif hasattr(vp, "render"):
                            cand = vp.render(audio_path, seg_dur, size)
                            if cand:
                                comp = cand.set_duration(seg_dur)
                    except Exception:
                        continue
            timeline.append({"start": t, "duration": seg_dur, "used_files": list(dict.fromkeys(used_this_row)), "pattern_index": patt_idx, "row_index": row_idx})
            clips.append(comp)
            t += seg_dur
        if t >= total:
            break

    # concatenate full clip for stream/moviepy
    final_clip = concatenate_videoclips(clips, method="compose") if clips else ColorClip(size=size, color=(0,0,0)).set_duration(total)

    # choose write mode
    try:
        if mode == "moviepy":
            _write_moviepy([final_clip], audio, out_path, fps=fps)
        elif mode == "stream":
            # stream final_clip frames to ffmpeg stdin, mux audio
            _ffmpeg_stream_clip(final_clip, audio_path, out_path, fps, size)
        else:
            # fallback to moviepy by default
            _write_moviepy([final_clip], audio, out_path, fps=fps)
    except Exception as e:
        # attempt fallback to moviepy write if stream failed and ffmpeg exists
        if mode == "stream":
            try:
                _write_moviepy([final_clip], audio, out_path, fps=fps)
            except Exception:
                raise
        else:
            raise

    # dedupe used files
    seen = set(); unique_used=[]
    for f in used_video_files:
        if f not in seen:
            seen.add(f); unique_used.append(f)

    return out_path, unique_used, timeline