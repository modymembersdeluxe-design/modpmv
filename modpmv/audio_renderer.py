"""
Audio renderer V4 Deluxe — mapping patterns -> pydub timeline, plugin chain, caching.
"""
from pydub import AudioSegment
from typing import List, Optional, Dict, Any
import os
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
        if idx < 0 or idx >= len(patterns): continue
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
                        seg = _load_audio(file_path)
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

def export_audio_segment(seg: AudioSegment, out_path: str, bitrate: str = "192k"):
    ensure_dir(os.path.dirname(out_path) or ".")
    fmt = os.path.splitext(out_path)[1].lstrip(".") or "mp3"
    seg.export(out_path, format=fmt, bitrate=bitrate)