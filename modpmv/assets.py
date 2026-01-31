"""Asset resolution helpers (audio, video, image)."""
import os
from typing import Optional, List, Tuple

AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

def _find(base: str, folders: List[str], exts: Tuple[str,...]) -> Optional[str]:
    if not base:
        return None
    key = base.lower()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            nm, ext = os.path.splitext(fname.lower())
            if ext in exts and (nm == key or nm.startswith(key) or key in nm):
                return os.path.join(folder, fname)
    return None

def find_audio_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find(sample_name, folders, AUDIO_EXTS)

def find_video_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find(sample_name, folders, VIDEO_EXTS)

def list_assets(folder: str, exts=()):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts]