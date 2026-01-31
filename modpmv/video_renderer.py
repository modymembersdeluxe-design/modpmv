"""
Video renderer V4 Deluxe — per-channel composer, ffmpeg concat pipeline, preview helper.

Two main modes:
- moviepy: compose and write via moviepy (convenient)
- ffmpeg: write per-row short files and use ffmpeg concat to stitch them (faster for long timelines)
"""
import os, random, subprocess, tempfile, shutil
from typing import List, Optional, Tuple, Dict, Any
from moviepy.editor import (AudioFileClip, VideoFileClip, ImageClip, ColorClip,
                            concatenate_videoclips, CompositeVideoClip)
from .assets import find_video_for_sample, list_assets
from .audio_renderer import render_audio_from_module_data, export_audio_segment
from .utils import ensure_dir

DEFAULT_ROW_SECONDS = 0.25
DEFAULT_SIZE = (1280,720)

def _image_clip_for_row(image_folders: List[str], duration: float, size: Tuple[int,int]):
    images=[]
    for f in image_folders:
        images += list_assets(f, exts=(".png",".jpg",".jpeg",".bmp"))
    if images:
        c = random.choice(images)
        return ImageClip(c).resize(newsize=size).set_duration(duration)
    return ColorClip(size=size, color=(10,10,10)).set_duration(duration)

def _write_moviepy(clips, audio, out_path: str, fps:int=24):
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    ensure_dir(os.path.dirname(out_path) or ".")
    video.write_videofile(out_path, fps=fps, audio_codec="aac")
    try: video.close()
    except Exception: pass

def _ffmpeg_concat(video_files: List[str], out_path: str, fps:int=24, audio_file: Optional[str]=None):
    """
    Simple ffmpeg concat via file list. Expects all inputs to share same codec/format or be safe to concat with ffmpeg.
    Writes a temporary 'inputs.txt' and calls ffmpeg -f concat -safe 0 -i inputs.txt -c copy out_path
    If audio_file is provided, mux audio afterwards.
    Note: For production, prefer re-encoding or consistent frame sizes; this is a pragmatic approach.
    """
    ensure_dir(os.path.dirname(out_path) or ".")
    tmpdir = tempfile.mkdtemp(prefix="modpmv_ff_")
    listfile = os.path.join(tmpdir, "inputs.txt")
    with open(listfile, "w", encoding="utf-8") as fh:
        for vf in video_files:
            fh.write(f"file '{os.path.abspath(vf).replace('\'','\\'')}'\n")
    # Try concat demuxer
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # fallback: try re-encoding with standard codecs
        cmd2 = ["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c:v","libx264","-preset","fast","-crf","18", out_path]
        proc2 = subprocess.run(cmd2, capture_output=True, text=True)
        if proc2.returncode != 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise RuntimeError(f"ffmpeg concat failed: {proc2.stderr}\n{proc.stderr}")
    # if audio_file provided, mux audio
    if audio_file and os.path.exists(audio_file):
        mux_out = out_path.replace(".mp4","_mux.mp4")
        cmd3 = ["ffmpeg","-y","-i", out_path, "-i", audio_file, "-c:v","copy","-c:a","aac", "-map","0:v:0","-map","1:a:0", mux_out]
        proc3 = subprocess.run(cmd3, capture_output=True, text=True)
        if proc3.returncode == 0:
            shutil.move(mux_out, out_path)
        else:
            # keep original but signal warning
            pass
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
                                  mode: str = "moviepy") -> Tuple[str, List[str]]:
    audio = AudioFileClip(audio_path)
    total = audio.duration
    clips = []
    used = []
    channels = int(module_data.get("channels",32))
    patterns = module_data.get("patterns", [])
    order = module_data.get("order", list(range(len(patterns))))
    t = 0.0

    # Mode "ffmpeg": write per-row short mp4s and concat them via ffmpeg. We'll write temp per-row mp4s in a tmpdir.
    temp_files = []
    tmpdir = None
    if mode == "ffmpeg":
        tmpdir = tempfile.mkdtemp(prefix="modpmv_rows_")

    for patt_idx in order:
        if patt_idx < 0 or patt_idx >= len(patterns): continue
        pattern = patterns[patt_idx]
        for row in pattern:
            if t >= total: break
            seg_dur = min(row_seconds, total - t)
            per_channel_clips = []
            for ch in range(channels):
                token = row[ch] if ch < len(row) else "REST"
                chosen = None
                if isinstance(token, str) and token.upper().startswith("SAMPLE:"):
                    chosen = token.split(":",1)[1]
                clip = None
                if chosen:
                    vf = find_video_for_sample(chosen, video_asset_folders)
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
                            used.append(vf)
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
                per_channel_clips.append((ch, clip))
            comp = CompositeVideoClip([c for _,c in sorted(per_channel_clips, key=lambda x:x[0])], size=size).set_duration(seg_dur)
            if visual_plugins:
                for vp in visual_plugins:
                    try:
                        if hasattr(vp, "apply"): comp = vp.apply(comp)
                        elif hasattr(vp, "render"):
                            cand = vp.render(audio_path, seg_dur, size)
                            if cand: comp = cand.set_duration(seg_dur)
                    except Exception:
                        continue
            if mode == "ffmpeg":
                # write short mp4 for this row
                fname = os.path.join(tmpdir, f"row_{len(temp_files):05d}.mp4")
                comp.write_videofile(fname, fps=fps, audio=False, verbose=False, logger=None)
                temp_files.append(fname)
            else:
                clips.append(comp)
            t += seg_dur
        if t >= total:
            break

    if mode == "moviepy":
        if not clips:
            clips = [ColorClip(size=size, color=(0,0,0)).set_duration(total)]
        _write_moviepy(clips, audio, out_path, fps=fps)
    else:
        # concat via ffmpeg (temp_files -> out_path), then mux audio
        if not temp_files:
            # fallback to single color clip
            tmp_single = os.path.join(tmpdir, "blank.mp4")
            ColorClip(size=size, color=(0,0,0)).set_duration(total).write_videofile(tmp_single, fps=fps, audio=False, verbose=False, logger=None)
            temp_files = [tmp_single]
        # concat and mux audio
        _ffmpeg_concat(temp_files, out_path, fps=fps, audio_file=audio_path)
        # clean temp
        shutil.rmtree(tmpdir, ignore_errors=True)

    try: audio.close()
    except Exception: pass
    uniq=[]; seen=set()
    for x in used:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return out_path, uniq

def render_preview(module_path: str,
                   audio_asset_folders: List[str],
                   video_asset_folders: List[str],
                   image_asset_folders: List[str],
                   preview_seconds: float = 6.0,
                   out_path: str = "output/preview.mp4",
                   size: Tuple[int,int] = (640,360),
                   visual_plugins: Optional[List] = None,
                   mode: str = "moviepy") -> str:
    from .mod_parser import parse
    module_data = parse(module_path)
    audio_seg = render_audio_from_module_data(module_data, audio_asset_folders, row_duration_ms=int(1000*DEFAULT_ROW_SECONDS))
    preview_ms = int(preview_seconds*1000)
    if len(audio_seg) > preview_ms:
        audio_seg = audio_seg[:preview_ms]
    elif len(audio_seg) < preview_ms:
        if len(audio_seg) > 0:
            need = preview_ms - len(audio_seg)
            audio_seg = audio_seg + audio_seg[:need]
        else:
            from pydub import AudioSegment
            audio_seg = AudioSegment.silent(duration=preview_ms)
    ensure_dir(os.path.dirname(out_path) or ".")
    preview_audio_path = out_path.replace(".mp4", ".mp3")
    export_audio_segment(audio_seg, preview_audio_path)
    render_video_from_module_data(module_data, preview_audio_path, video_asset_folders, image_asset_folders, out_path, fps=24, size=size, row_seconds=DEFAULT_ROW_SECONDS, visual_plugins=visual_plugins, mode=mode)
    try:
        if os.name == "nt":
            os.startfile(out_path)
        else:
            import shutil, subprocess
            opener = shutil.which("xdg-open") or shutil.which("open")
            if opener:
                subprocess.Popen([opener, out_path])
    except Exception:
        pass
    return out_path