"""
YTPMV exporter V3: copy audio/video and only truly used video sample files, write manifest with timeline mapping.
"""
import os, shutil, json
from typing import List, Dict, Any
from .utils import ensure_dir

def export_ytpmv_package(module_data: Dict[str, Any],
                         audio_path: str,
                         video_path: str,
                         used_video_files: List[str],
                         out_folder: str,
                         manifest_name: str = "manifest.json") -> str:
    ensure_dir(out_folder)
    dest_audio = os.path.join(out_folder, os.path.basename(audio_path))
    dest_video = os.path.join(out_folder, os.path.basename(video_path))
    shutil.copy2(audio_path, dest_audio)
    shutil.copy2(video_path, dest_video)
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
    manifest: Dict[str, Any] = {
        "module_title": module_data.get("title"),
        "audio": os.path.basename(dest_audio),
        "video": os.path.basename(dest_video),
        "copied_video_clips": copied,
        "order": module_data.get("order"),
        "patterns_count": len(module_data.get("patterns", [])),
    }
    with open(os.path.join(out_folder, manifest_name), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return os.path.join(out_folder, manifest_name)