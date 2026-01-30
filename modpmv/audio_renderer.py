"""
Audio renderer (V2) — assemble audio according to module patterns, support audio plugin chain.
"""
from pydub import AudioSegment
import os
from typing import List, Optional
from modpmv.mod_parser import Module
from modpmv.assets import find_audio_for_sample

DEFAULT_ROW_MS = 250

def _load_sample(path: str) -> AudioSegment:
    return AudioSegment.from_file(path)

def render_audio_from_module(module: Module,
                             audio_asset_folders: List[str],
                             row_duration_ms: int = DEFAULT_ROW_MS) -> AudioSegment:
    out = AudioSegment.silent(duration=0)
    for idx in (module.order or list(range(len(module.patterns)))):
        if idx < 0 or idx >= len(module.patterns):
            continue
        pattern = module.patterns[idx]
        for row in pattern.rows:
            segments = []
            for tok in row:
                if tok.upper() == "REST":
                    continue
                if tok.upper().startswith("SAMPLE:"):
                    name = tok.split(":",1)[1]
                    sample_decl = module.samples.get(name)
                    file_path = None
                    if sample_decl and sample_decl.file and os.path.exists(sample_decl.file):
                        file_path = sample_decl.file
                    else:
                        file_path = find_audio_for_sample(name, audio_asset_folders)
                    if file_path and os.path.exists(file_path):
                        seg = _load_sample(file_path)
                        # normalize to row length
                        if len(seg) > row_duration_ms:
                            seg = seg[:row_duration_ms]
                        elif len(seg) < row_duration_ms and len(seg) > 0:
                            seg = seg * (row_duration_ms // len(seg)) + seg[:(row_duration_ms % len(seg))]
                        else:
                            seg = seg.set_duration(row_duration_ms) if hasattr(seg, "set_duration") else seg
                        segments.append(seg)
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

def apply_audio_plugins(audio: AudioSegment, audio_plugins: List) -> AudioSegment:
    seg = audio
    for plugin in audio_plugins:
        try:
            seg = plugin.process(seg)
        except Exception:
            continue
    return seg

def export_audio_segment(seg: AudioSegment, out_path: str, bitrate: str = "192k"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fmt = os.path.splitext(out_path)[1].lstrip(".") or "mp3"
    seg.export(out_path, format=fmt, bitrate=bitrate)