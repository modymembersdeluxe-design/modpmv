"""Asset resolution helpers (audio, video, images)."""
import os
from typing import Optional, List, Tuple

AUDIO_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".avi")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

def _find_in_folders(base_name: str, folders: List[str], exts: Tuple[str,...]) -> Optional[str]:
    if not base_name:
        return None
    base = base_name.lower()
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            nm, ext = os.path.splitext(fname.lower())
            if ext in exts:
                if nm == base or nm.startswith(base) or base in nm:
                    return os.path.join(folder, fname)
    return None

def find_audio_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find_in_folders(sample_name, folders, AUDIO_EXTS)

def find_video_for_sample(sample_name: str, folders: List[str]) -> Optional[str]:
    return _find_in_folders(sample_name, folders, VIDEO_EXTS)

def list_assets(folder: str, exts=()):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts]