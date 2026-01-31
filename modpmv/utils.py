"""Utility helpers used across ModPMV V3."""
import os
import json
import hashlib
from typing import Any

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def write_json(path: str, data: Any):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

def stable_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()