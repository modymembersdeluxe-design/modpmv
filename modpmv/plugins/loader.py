"""
Plugin discovery & manifest (V3):
- discover_plugins(plugin_folder) -> {"audio": {...}, "visual": {...}}
- list_plugins_manifest(plugin_folder) -> list of metadata dicts (name,type,description,tags,class)
Supports:
- entry points (modpmv.plugins.audio / modpmv.plugins.visual)
- local plugins folder (plugins/audio, plugins/visual)
- examples/plugins used by default in GUI
"""
import os
import sys
import importlib.util
from importlib.metadata import entry_points
from typing import Dict, Any, List, Optional
from .base import AudioPlugin, VisualPlugin

def _load_from_entry_points(group: str) -> Dict[str, Any]:
    found = {}
    try:
        eps = entry_points()
        items = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
        for ep in items:
            try:
                cls = ep.load()
                key = getattr(cls, "name", ep.name)
                found[key] = cls
            except Exception:
                continue
    except Exception:
        pass
    return found

def _load_from_folder(folder: str) -> Dict[str, Any]:
    plugins = {}
    if not os.path.isdir(folder):
        return plugins
    sys.path.insert(0, folder)
    for fname in os.listdir(folder):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(folder, fname)
        name = os.path.splitext(fname)[0]
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            for attr in dir(mod):
                obj = getattr(mod, attr)
                try:
                    if isinstance(obj, type) and issubclass(obj, (AudioPlugin, VisualPlugin)) and obj not in (AudioPlugin, VisualPlugin):
                        plugins[getattr(obj, "name", f"{name}.{attr}")] = obj
                except Exception:
                    continue
        except Exception:
            continue
    try:
        sys.path.pop(0)
    except Exception:
        pass
    return plugins

def discover_plugins(plugin_folder: Optional[str] = "plugins") -> Dict[str, Dict[str, Any]]:
    audio = {}
    visual = {}
    audio.update(_load_from_entry_points("modpmv.plugins.audio"))
    visual.update(_load_from_entry_points("modpmv.plugins.visual"))
    if plugin_folder:
        audio.update(_load_from_folder(os.path.join(plugin_folder, "audio")))
        visual.update(_load_from_folder(os.path.join(plugin_folder, "visual")))
        # flat fallback
        audio.update(_load_from_folder(plugin_folder))
        visual.update(_load_from_folder(plugin_folder))
    return {"audio": audio, "visual": visual}

def list_plugins_manifest(plugin_folder: Optional[str] = "plugins") -> List[Dict[str, Any]]:
    discovered = discover_plugins(plugin_folder)
    manifest = []
    for ptype in ("audio","visual"):
        for name, cls in discovered.get(ptype, {}).items():
            try:
                meta = {
                    "name": getattr(cls, "name", name),
                    "type": ptype,
                    "description": getattr(cls, "description", "") or "",
                    "tags": getattr(cls, "tags", []) or [],
                    "version": getattr(cls, "version", "0.0.1"),
                    "class": cls
                }
                manifest.append(meta)
            except Exception:
                continue
    manifest.sort(key=lambda m: (m["type"], m["name"]))
    return manifest