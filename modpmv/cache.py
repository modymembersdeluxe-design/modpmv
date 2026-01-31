"""File-based cache for previews, intermediates and job artifacts."""
import os, shutil
from typing import Optional
from .utils import stable_hash, ensure_dir

CACHE_ROOT = ".modpmv_cache"

def path_for(key: str, filename: str) -> str:
    ensure_dir(CACHE_ROOT)
    k = stable_hash(key)
    d = os.path.join(CACHE_ROOT, k)
    ensure_dir(d)
    return os.path.join(d, filename)

def has(key: str, filename: str) -> bool:
    return os.path.exists(path_for(key, filename))

def clear():
    if os.path.isdir(CACHE_ROOT):
        shutil.rmtree(CACHE_ROOT)