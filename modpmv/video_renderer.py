"""
Resilient video renderer for ModPMV V4 Deluxe.

Improvements:
- Robust ffmpeg detection and clear fallbacks between `moviepy` and `ffmpeg` modes.
- Per-row timeline mapping returned so exporter can record precise timestamps.
- Safe temp file handling and cleanup.
- Graceful fallbacks: if moviepy write fails, automatically attempt ffmpeg concat path (if ffmpeg available).
- Better error messages for missing ffmpeg / moviepy.
- Returns (out_path, used_video_files, timeline) where timeline is a list of {start, duration, used_files, pattern_index, row_index}.

Notes:
- Requires moviepy & ffmpeg (system binary or imageio-ffmpeg).
"""
import os
import random
import subprocess
import tempfile
import shutil
from typing import List, Optional, Tuple, Dict, Any
from moviepy.editor import (AudioFileClip, VideoFileClip, ImageClip, ColorClip,
                            concatenate_videoclips, CompositeVideoClip)
from .assets import find_video_for_sample, list_assets
from .audio_renderer import render_audio_from_module_data, export_audio_segment
from .utils import ensure_dir

DEFAULT_ROW_SECONDS = 0.25
DEFAULT_SIZE = (1280, 720)

def _ffmpeg_exe() -> Optional[str]:
    # prefer system ffmpeg, fall back to imageio-ffmpeg if available
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
    # moviepy may be verbose and sometimes fail on large outputs -> caller should catch exceptions
    video.write_videofile(out_path, fps=fps, audio_codec="aac")
    try: video.close()
    except Exception: pass

def _ffmpeg_concat(video_files: List[str], out_path: str, audio_file: Optional[str]=None):
    """
    Concat via ffmpeg using concat demuxer (safer) then optionally mux audio.
    Raises RuntimeError on failure with stderr included.
    """
    ff = _ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg not found on PATH and imageio-ffmpeg not available.")

    tmpdir = tempfile.mkdtemp(prefix="modpmv_ff_")
    listfile = os.path.join(tmpdir, "inputs.txt")
    try:
        # Write file list for concat demuxer. Use ffmpeg-safe escaping by writing absolute paths.
        with open(listfile, "w", encoding="utf-8") as fh:
            for vf in video_files:
                fh.write(f"file '{os.path.abspath(vf).replace(\"'\", \"'\\\"'\\\"\")}'\n")
        # Try concat demuxer (copy)
        cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            # try re-encoding fallback
            cmd2 = [ff, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c:v", "libx264", "-preset", "fast", "-crf", "18", out_path]
            proc2 = subprocess.run(cmd2, capture_output=True, text=True)
            if proc2.returncode != 0:
                raise RuntimeError(f"ffmpeg concat failed:\ncopy stderr:\n{proc.stderr}\nre-encode stderr:\n{proc2.stderr}")
        # If audio file provided, mux audio (re-mux)
        if audio_file and os.path.exists(audio_file):
            mux_out = out_path.replace(".mp4", "_mux.mp4")
            cmd3 = [ff, "-y", "-i", out_path, "-i", audio_file, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", mux_out]
            proc3 = subprocess.run(cmd3, capture_output=True, text=True)
            if proc3.returncode == 0:
                shutil.move(mux_out, out_path)
            else:
                # keep original and warn via exception path optionally
                raise RuntimeError(f"ffmpeg mux failed: {proc3.stderr}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

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
    Render a full video for module_data.
    Returns (out_path, used_video_files, timeline)
    timeline: list of {start:float, duration:float, used_files:[str], pattern_index:int, row_index:int}
    """
    # Basic checks
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio path not found: {audio_path}")

    audio = AudioFileClip(audio_path)
    total = audio.duration
    clips = []
    used_video_files: List[str] = []
    timeline: List[Dict[str,Any]] = []

    channels = int(module_data.get("channels", 32))
    patterns = module_data.get("patterns", [])
    order = module_data.get("order", list(range(len(patterns))))
    t = 0.0

    # If ffmpeg mode requested but ffmpeg missing, fallback to moviepy mode
    ff_available = _ffmpeg_exe() is not None
    if mode == "ffmpeg" and not ff_available:
        mode = "moviepy"

    # For ffmpeg mode collect per-row temp files
    temp_files: List[str] = []
    tmpdir = tempfile.mkdtemp(prefix="modpmv_rows_") if mode == "ffmpeg" else None

    try:
        for patt_idx in order:
            if patt_idx < 0 or patt_idx >= len(patterns):
                continue
            pattern = patterns[patt_idx]
            for row_idx, row in enumerate(pattern):
                if t >= total:
                    break
                seg_dur = min(row_seconds, total - t)
                per_channel_clips = []
                used_this_row: List[str] = []

                for ch in range(channels):
                    token = row[ch] if ch < len(row) else "REST"
                    chosen_sample = None
                    if isinstance(token, str) and token.upper().startswith("SAMPLE:"):
                        chosen_sample = token.split(":", 1)[1]
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
                                        rem = seg_dur - repeats * v.duration
                                        if rem > 0:
                                            parts.append(v.subclip(0, rem))
                                        v = concatenate_videoclips(parts)
                                    else:
                                        v = v.set_duration(seg_dur)
                                channel_clip = v.resize(newsize=size).set_duration(seg_dur)
                                used_this_row.append(vf)
                                used_video_files.append(vf)
                            except Exception:
                                channel_clip = None
                    if channel_clip is None:
                        channel_clip = _image_clip_for_row(image_asset_folders, seg_dur, size)
                        tint = ((ch * 37) % 255, (ch * 59) % 255, (ch * 83) % 255)
                        bar = ColorClip(size=(int(size[0] * 0.15), int(size[1] * 0.07)), color=tint).set_duration(seg_dur)
                        pos_x = int((ch % 8) * (size[0] * 0.02)); pos_y = int((ch // 8) * (size[1] * 0.06))
                        bar = bar.set_pos((pos_x, pos_y))
                        channel_clip = CompositeVideoClip([channel_clip, bar], size=size).set_duration(seg_dur)

                    def pos_fn_factory(ci):
                        def pos_fn(tt):
                            x = int((ci % 8) * (size[0] * 0.11)); y = int((ci // 8) * (size[1] * 0.12))
                            return (x, y)
                        return pos_fn

                    channel_clip = channel_clip.set_pos(pos_fn_factory(ch))
                    channel_clip = channel_clip.set_opacity(0.9 - min(0.6, ch * 0.01))
                    per_channel_clips.append((ch, channel_clip))

                # Composite per-row
                comp = CompositeVideoClip([c for _, c in sorted(per_channel_clips, key=lambda x: x[0])], size=size).set_duration(seg_dur)
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

                # record timeline entry
                timeline.append({
                    "start": t,
                    "duration": seg_dur,
                    "used_files": list(dict.fromkeys(used_this_row)),
                    "pattern_index": patt_idx,
                    "row_index": row_idx
                })

                # Output handling per mode
                if mode == "ffmpeg":
                    fname = os.path.join(tmpdir, f"row_{len(temp_files):05d}.mp4")
                    # Write short mp4 without audio; moviepy may raise; let caller fallback
                    comp.write_videofile(fname, fps=fps, audio=False, verbose=False, logger=None)
                    temp_files.append(fname)
                else:
                    clips.append(comp)

                t += seg_dur

            if t >= total:
                break

        # Finish render
        if mode == "moviepy":
            if not clips:
                clips = [ColorClip(size=size, color=(0,0,0)).set_duration(total)]
            try:
                _write_moviepy(clips, audio, out_path, fps=fps)
            except Exception as e:
                # Try fallback to ffmpeg concat if available
                if ff_available:
                    # write per-row temp files (we don't have them yet) -> generate using moviepy per-row writes
                    tmpdir2 = tempfile.mkdtemp(prefix="modpmv_rows_fallback_")
                    generated = []
                    try:
                        # write each clip individually
                        for idx, clip in enumerate(clips):
                            tmpf = os.path.join(tmpdir2, f"row_fb_{idx:05d}.mp4")
                            clip.write_videofile(tmpf, fps=fps, audio=False, verbose=False, logger=None)
                            generated.append(tmpf)
                        _ffmpeg_concat(generated, out_path, audio_file=audio_path)
                    finally:
                        shutil.rmtree(tmpdir2, ignore_errors=True)
                else:
                    raise RuntimeError(f"moviepy.write_videofile failed and ffmpeg not available to fallback: {e}")
        else:
            # ffmpeg mode: concat temp_files and mux audio
            if not temp_files:
                # generate single blank clip to mux
                tmp_single = os.path.join(tmpdir, "blank.mp4")
                ColorClip(size=size, color=(0,0,0)).set_duration(total).write_videofile(tmp_single, fps=fps, audio=False, verbose=False, logger=None)
                temp_files = [tmp_single]
            _ffmpeg_concat(temp_files, out_path, audio_file=audio_path)

    finally:
        try:
            audio.close()
        except Exception:
            pass
        # cleanup temp_files & tmpdir if present (ffmpeg mode)
        try:
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    # dedupe used file list preserving order
    seen = set()
    unique_used = []
    for f in used_video_files:
        if f not in seen:
            seen.add(f)
            unique_used.append(f)

    return out_path, unique_used, timeline

def render_preview(module_path: str,
                   audio_asset_folders: List[str],
                   video_asset_folders: List[str],
                   image_asset_folders: List[str],
                   preview_seconds: float = 6.0,
                   out_path: str = "output/preview.mp4",
                   size: Tuple[int,int] = (640,360),
                   visual_plugins: Optional[List] = None,
                   mode: str = "moviepy") -> str:
    """
    Parse the module (via mod_parser.parse upstream), render a short preview and open it.
    """
    from .mod_parser import parse
    from pydub import AudioSegment
    module_data = parse(module_path)
    # render audio for preview length
    audio_seg = render_audio_from_module_data(module_data, audio_asset_folders, row_duration_ms=int(1000 * DEFAULT_ROW_SECONDS))
    preview_ms = int(preview_seconds * 1000)
    if len(audio_seg) > preview_ms:
        audio_seg = audio_seg[:preview_ms]
    elif len(audio_seg) < preview_ms:
        if len(audio_seg) > 0:
            need = preview_ms - len(audio_seg)
            audio_seg = audio_seg + audio_seg[:need]
        else:
            audio_seg = AudioSegment.silent(duration=preview_ms)
    ensure_dir(os.path.dirname(out_path) or ".")
    preview_audio_path = out_path.replace(".mp4", ".mp3")
    export_audio_segment(audio_seg, preview_audio_path)
    # render video (may raise, let caller handle)
    out, used, timeline = render_video_from_module_data(module_data, preview_audio_path, video_asset_folders, image_asset_folders, out_path, fps=24, size=size, row_seconds=DEFAULT_ROW_SECONDS, visual_plugins=visual_plugins, mode=mode)
    # try to open with default viewer
    try:
        if os.name == "nt":
            os.startfile(out)
        else:
            import shutil, subprocess
            opener = shutil.which("xdg-open") or shutil.which("open")
            if opener:
                subprocess.Popen([opener, out])
    except Exception:
        pass
    return out