"""
Video renderer V5 Deluxe — streaming ffmpeg mode + robust fallbacks.

This file includes:
- render_video_from_module_data(...) -> (out_path, used_video_files, timeline)
- render_preview(...) -> out_path (creates a short preview audio/video and attempts to open it)

Fix: ensure render_preview is defined so GUI can import it without ImportError.
"""
import os
import random
import subprocess
import tempfile
import shutil
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
    """
    ff = _ffmpeg_exe()
    if ff is None:
        raise RuntimeError("ffmpeg not found for stream mode.")
    w, h = size
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
        if duration is None:
            raise RuntimeError("Clip duration is None; cannot stream.")
        frame_count = max(1, int(duration * fps))
        for i in range(frame_count):
            t = i / fps
            frame = clip.get_frame(t)  # HxWx3 uint8
            # Ensure frame is HxW matching requested size
            if frame.shape[0] != h or frame.shape[1] != w:
                # use moviepy to resize a single-frame clip (cheap)
                from moviepy.editor import ImageClip
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

def _ffmpeg_concat(video_files: List[str], out_path: str, audio_file: Optional[str]=None):
    ff = _ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg not found on PATH and imageio-ffmpeg not available.")
    tmpdir = tempfile.mkdtemp(prefix="modpmv_ff_")
    listfile = os.path.join(tmpdir, "inputs.txt")
    try:
        with open(listfile, "w", encoding="utf-8") as fh:
            for vf in video_files:
                safe = os.path.abspath(vf).replace("'", "\\'")
                fh.write("file '{}'\n".format(safe))
        cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            cmd2 = [ff, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c:v", "libx264", "-preset", "fast", "-crf", "18", out_path]
            proc2 = subprocess.run(cmd2, capture_output=True, text=True)
            if proc2.returncode != 0:
                raise RuntimeError(f"ffmpeg concat failed:\ncopy stderr:\n{proc.stderr}\nre-encode stderr:\n{proc2.stderr}")
        if audio_file and os.path.exists(audio_file):
            mux_out = out_path.replace(".mp4", "_mux.mp4")
            cmd3 = [ff, "-y", "-i", out_path, "-i", audio_file, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", mux_out]
            proc3 = subprocess.run(cmd3, capture_output=True, text=True)
            if proc3.returncode == 0:
                shutil.move(mux_out, out_path)
            else:
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
    Render video. Modes: "moviepy", "ffmpeg" (concat), "stream" (ffmpeg stdin).
    Returns (out_path, used_video_files, timeline).
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
        mode = "moviepy"

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
                                used_this_row.append(vf); used_video_files.append(vf)
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
                if mode == "ffmpeg":
                    fname = os.path.join(tmpdir, f"row_{len(temp_files):05d}.mp4")
                    comp.write_videofile(fname, fps=fps, audio=False, verbose=False, logger=None)
                    temp_files.append(fname)
                else:
                    clips.append(comp)
                t += seg_dur
            if t >= total:
                break

        final_clip = concatenate_videoclips(clips, method="compose") if clips else ColorClip(size=size, color=(0,0,0)).set_duration(total)

        if mode == "moviepy":
            _write_moviepy([final_clip], audio, out_path, fps=fps)
        elif mode == "stream":
            _ffmpeg_stream_clip(final_clip, audio_path, out_path, fps, size)
        else:  # ffmpeg concat
            if not temp_files:
                tmp_single = os.path.join(tmpdir, "blank.mp4")
                ColorClip(size=size, color=(0,0,0)).set_duration(total).write_videofile(tmp_single, fps=fps, audio=False, verbose=False, logger=None)
                temp_files = [tmp_single]
            _ffmpeg_concat(temp_files, out_path, audio_file=audio_path)

    finally:
        try: audio.close()
        except Exception: pass
        try:
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    seen = set(); unique_used = []
    for f in used_video_files:
        if f not in seen:
            seen.add(f); unique_used.append(f)
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
    Convenience: parse module_path, render a short low-res preview of preview_seconds,
    write to out_path and attempt to open it (OS default).
    """
    from .mod_parser import parse
    from pydub import AudioSegment
    module_data = parse(module_path)
    # build preview audio
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
    # render short video
    out, used, timeline = render_video_from_module_data(module_data, preview_audio_path, video_asset_folders, image_asset_folders, out_path, fps=24, size=size, row_seconds=DEFAULT_ROW_SECONDS, visual_plugins=visual_plugins, mode=mode)
    # try to open
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