"""
Simple job queue for ModPMV Deluxe — JSON file backed.
"""
import os, json
from typing import Dict, Any, List
from .utils import ensure_dir

QUEUE_DIR = ".modpmv_jobs"
def _ensure():
    ensure_dir(QUEUE_DIR)

def push_job(job_id: str, job: Dict[str, Any]):
    _ensure()
    path = os.path.join(QUEUE_DIR, f"{job_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=2, ensure_ascii=False)

def list_jobs() -> List[str]:
    _ensure()
    return [f for f in os.listdir(QUEUE_DIR) if f.endswith(".json")]

def load_job(fn: str) -> Dict[str, Any]:
    path = os.path.join(QUEUE_DIR, fn); 
    with open(path, "r", encoding="utf-8") as fh: return json.load(fh)

def pop_job(fn: str):
    p = os.path.join(QUEUE_DIR, fn)
    if os.path.exists(p): os.remove(p)