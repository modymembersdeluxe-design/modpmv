"""
Simple file-based cache for rendered previews and intermediate audio files.
Cache keys are stable hashes of job parameters so preview runs reuse previous work.
"""
import os
from typing import Optional
from .utils import stable_hash, ensure_dir

CACHE_DIR = os.path.join(".modpmv_cache")

def cached_path_for_job(job_id: str, filename: str) -> str:
    ensure_dir(CACHE_DIR)
    key = stable_hash(job_id)
    d = os.path.join(CACHE_DIR, key)
    ensure_dir(d)
    return os.path.join(d, filename)

def exists_cached(job_id: str, filename: str) -> bool:
    return os.path.exists(cached_path_for_job(job_id, filename))

def clear_cache():
    import shutil
    if os.path.isdir(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)