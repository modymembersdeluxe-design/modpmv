"""
Simple plugin marketplace scaffolding: supports local registry JSON files describing plugin bundles.

This is a starter for future GUI integration (install/uninstall plugin packages).
"""
import os, json
from typing import List, Dict, Any
from .utils import ensure_dir

REGISTRY = "plugin_registry.json"

def load_registry(path: str = REGISTRY) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def save_registry(reg: List[Dict[str, Any]], path: str = REGISTRY):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, ensure_ascii=False)

def add_plugin_entry(meta: Dict[str, Any], path: str = REGISTRY):
    reg = load_registry(path)
    reg.append(meta)
    save_registry(reg, path)