"""
Asset helpers: locate audio/video/image assets matching sample names or files.
"""
import os
from typing import Optional, List

AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

def _find_in_folders(name: str, folders: List[str], exts: tuple) -> Optional[str]:
    if not name:
        return None
    base = name.lower()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            lc = fname.lower()
            nm, ext = os.path.splitext(lc)
            if ext in exts:
                if nm == base or nm.startswith(base) or base in nm:
                    return os.path.join(folder, fname)
    return None

def find_audio_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find_in_folders(sample_name, folders, AUDIO_EXTS)

def find_video_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find_in_folders(sample_name, folders, VIDEO_EXTS)

def list_assets(folder: str, exts: tuple) -> List[str]:
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts]