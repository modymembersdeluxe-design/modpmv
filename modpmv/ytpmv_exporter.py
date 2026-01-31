"""
YTPMV exporter V4 Deluxe — improved robustness and timeline mapping.

Exports:
- packaged audio & video files into out_folder
- copies only used video clips (best-effort)
- writes a manifest including timeline mappings (start/duration and used sample file names)
"""
import os
import shutil
import json
from typing import List, Dict, Any
from .utils import ensure_dir

def export_ytpmv_package(module_data: Dict[str, Any],
                         audio_path: str,
                         video_path: str,
                         used_video_files: List[str],
                         timeline: List[Dict[str, Any]],
                         out_folder: str,
                         manifest_name: str = "manifest.json") -> str:
    ensure_dir(out_folder)
    # copy audio/video
    dest_audio = os.path.join(out_folder, os.path.basename(audio_path))
    dest_video = os.path.join(out_folder, os.path.basename(video_path))
    shutil.copy2(audio_path, dest_audio)
    shutil.copy2(video_path, dest_video)
    # copy used video files into video_clips/
    clips_dir = os.path.join(out_folder, "video_clips")
    ensure_dir(clips_dir)
    copied = []
    for vf in (used_video_files or []):
        if os.path.exists(vf):
            dst = os.path.join(clips_dir, os.path.basename(vf))
            try:
                shutil.copy2(vf, dst)
                copied.append(os.path.relpath(dst, out_folder))
            except Exception:
                continue
    # Build manifest with timeline entries (include used clip basenames)
    manifest: Dict[str, Any] = {
        "module_title": module_data.get("title"),
        "audio": os.path.basename(dest_audio),
        "video": os.path.basename(dest_video),
        "copied_video_clips": copied,
        "order": module_data.get("order"),
        "patterns_count": len(module_data.get("patterns", [])),
        "timeline": []
    }
    for entry in (timeline or []):
        # map used_files to basenames if they were copied, otherwise absolute paths
        used = entry.get("used_files", [])
        used_mapped = []
        for u in used:
            bn = os.path.basename(u)
            rel = next((c for c in copied if os.path.basename(c) == bn), None)
            used_mapped.append(rel if rel else u)
        manifest["timeline"].append({
            "start": entry.get("start"),
            "duration": entry.get("duration"),
            "pattern_index": entry.get("pattern_index"),
            "row_index": entry.get("row_index"),
            "used_files": used_mapped
        })
    with open(os.path.join(out_folder, manifest_name), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return os.path.join(out_folder, manifest_name)