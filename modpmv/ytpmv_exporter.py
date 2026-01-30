"""
YTPMV exporter: copies generated audio/video and used assets into a package folder,
writes manifest describing timeline and module info.
"""
import os, shutil, json
from typing import List
from modpmv.mod_parser import Module

def export_ytpmv_package(module: Module,
                         audio_path: str,
                         video_path: str,
                         used_video_files: List[str],
                         out_folder: str,
                         manifest_name: str = "manifest.json") -> str:
    os.makedirs(out_folder, exist_ok=True)
    dest_audio = os.path.join(out_folder, os.path.basename(audio_path))
    dest_video = os.path.join(out_folder, os.path.basename(video_path))
    shutil.copy2(audio_path, dest_audio)
    shutil.copy2(video_path, dest_video)
    clips_dir = os.path.join(out_folder, "video_clips")
    os.makedirs(clips_dir, exist_ok=True)
    copied = []
    for vf in (used_video_files or []):
        if os.path.exists(vf):
            dst = os.path.join(clips_dir, os.path.basename(vf))
            try:
                shutil.copy2(vf, dst)
                copied.append(os.path.relpath(dst, out_folder))
            except Exception:
                continue
    manifest = {
        "module_title": module.title,
        "audio": os.path.basename(dest_audio),
        "video": os.path.basename(dest_video),
        "copied_video_clips": copied,
        "order": module.order,
        "patterns_count": len(module.patterns),
    }
    with open(os.path.join(out_folder, manifest_name), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return os.path.join(out_folder, manifest_name)