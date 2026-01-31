"""
Audio renderer V4/V5 — safe export helper.

- render_audio_from_module_data: map module_data -> pydub.AudioSegment timeline
- apply_audio_plugins: chain audio plugins (AudioEffectPlugin)
- export_audio_segment: robust export:
    - writes a WAV (always)
    - if the requested out_path extension is mp3 (or others), attempts to transcode WAV -> requested using ffmpeg (preferred)
    - falls back to pydub export if ffmpeg not available
    - verifies output file exists and is non-empty
"""
from pydub import AudioSegment
from typing import List, Optional, Dict, Any
import os
import subprocess
from .assets import find_audio_for_sample
from .utils import ensure_dir

DEFAULT_ROW_MS = 250

def _load_audio(path: str) -> AudioSegment:
    return AudioSegment.from_file(path)

def render_audio_from_module_data(module_data: Dict[str, Any],
                                  audio_asset_folders: List[str],
                                  row_duration_ms: int = DEFAULT_ROW_MS) -> AudioSegment:
    out = AudioSegment.silent(duration=0)
    patterns = module_data.get("patterns", [])
    order = module_data.get("order", list(range(len(patterns))))
    channels = int(module_data.get("channels", 32))
    for idx in order:
        if idx < 0 or idx >= len(patterns):
            continue
        patt = patterns[idx]
        for row in patt:
            segments=[]
            for tok in row[:channels]:
                if isinstance(tok, str) and tok.upper().startswith("SAMPLE:"):
                    name = tok.split(":",1)[1]
                    sdecl = module_data.get("samples",{}).get(name)
                    file_path = sdecl.get("file") if sdecl else None
                    if not file_path:
                        file_path = find_audio_for_sample(name, audio_asset_folders)
                    if file_path and os.path.exists(file_path):
                        seg=_load_audio(file_path)
                        if len(seg) > row_duration_ms: seg = seg[:row_duration_ms]
                        elif len(seg) < row_duration_ms and len(seg)>0:
                            seg = seg * (row_duration_ms // len(seg)) + seg[:(row_duration_ms % len(seg))]
                        segments.append(seg)
                    else:
                        segments.append(AudioSegment.silent(duration=row_duration_ms))
                else:
                    segments.append(AudioSegment.silent(duration=row_duration_ms))
            if segments:
                mixed = segments[0]
                for s in segments[1:]:
                    mixed = mixed.overlay(s)
                if len(mixed) < row_duration_ms:
                    mixed = mixed + AudioSegment.silent(duration=(row_duration_ms - len(mixed)))
                elif len(mixed) > row_duration_ms:
                    mixed = mixed[:row_duration_ms]
                out = out.append(mixed, crossfade=0)
            else:
                out = out.append(AudioSegment.silent(duration=row_duration_ms), crossfade=0)
    return out

def apply_audio_plugins(audio: AudioSegment, plugins: List) -> AudioSegment:
    seg = audio
    for p in plugins:
        try:
            seg = p.process(seg)
        except Exception:
            continue
    return seg

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

def export_audio_segment(seg: AudioSegment, out_path: str, bitrate: str = "192k"):
    """
    Robust export:
      - always write a temporary WAV
      - if out_path extension is mp3 (or other compressed), try ffmpeg to transcode WAV -> target
      - fall back to pydub export if ffmpeg not available
      - verify output file exists and non-empty, raise helpful error otherwise
    """
    ensure_dir(os.path.dirname(out_path) or ".")
    out_ext = os.path.splitext(out_path)[1].lower().lstrip(".")
    base = os.path.splitext(out_path)[0]
    wav_path = base + ".wav"
    # Export WAV first (reliable)
    seg.export(wav_path, format="wav")
    # If user wants WAV, we're done
    if out_ext in ("wav", ""):
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            # If out_path is not exactly wav_path, copy/rename
            if os.path.abspath(wav_path) != os.path.abspath(out_path):
                try:
                    import shutil
                    shutil.copy2(wav_path, out_path)
                except Exception:
                    pass
            return
        else:
            raise IOError(f"Failed to write WAV to {wav_path}")
    # Otherwise, transcode WAV -> requested format (prefer ffmpeg)
    ff = _ffmpeg_exe()
    if ff and out_ext in ("mp3","m4a","aac","ogg","flac","wav","wavpcm"):
        # build ffmpeg command
        args = [ff, "-y", "-i", wav_path]
        # codec choices - mp3 via libmp3lame, others default
        if out_ext == "mp3":
            args += ["-codec:a", "libmp3lame", "-b:a", bitrate, out_path]
        elif out_ext in ("m4a","aac"):
            args += ["-c:a", "aac", "-b:a", bitrate, out_path]
        elif out_ext == "ogg":
            args += ["-c:a", "libvorbis", "-b:a", bitrate, out_path]
        elif out_ext == "flac":
            args += ["-c:a", "flac", out_path]
        else:
            # generic copy/re-encode
            args += [out_path]
        try:
            proc = subprocess.run(args, capture_output=True, text=True)
            if proc.returncode != 0:
                # ffmpeg failed; fall back to pydub export below
                pass
            else:
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    # successful transcode
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                    return
        except Exception:
            pass
    # Fallback: use pydub export directly to requested format
    try:
        seg.export(out_path, format=out_ext, bitrate=bitrate)
    except Exception as e:
        raise IOError(f"Failed to export audio to {out_path}: {e}")
    # verify
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise IOError(f"Exported audio file {out_path} is missing or empty. Check ffmpeg/pydub availability.")