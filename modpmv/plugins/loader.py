"""
Plugin discovery + loading for ModPMV.

Behavior:
 - First, load entry points (groups: modpmv.plugins.audio, modpmv.plugins.visual)
 - Next, scan a `plugins` directory (path provided) for .py files and import them.
 - Return mapping: {'audio': {name: cls_or_instance}, 'visual': {...}}
"""
from importlib import import_module
import importlib.util
import os
import sys
from typing import Dict, Any, Optional
from importlib.metadata import entry_points
from modpmv.plugins.base import AudioPlugin, VisualPlugin

def _load_from_entry_points(group: str) -> Dict[str, Any]:
    plugins = {}
    try:
        eps = entry_points()
        groups = []
        # entry_points() returns a mapping on py3.10+; handle both shapes:
        if hasattr(eps, "select"):
            groups = eps.select(group=group)
        else:
            groups = eps.get(group, []) if isinstance(eps, dict) else []
    except Exception:
        groups = []
    for ep in groups:
        try:
            obj = ep.load()
            key = getattr(obj, "name", ep.name)
            plugins[key] = obj
        except Exception:
            # ignore faulty plugin loads; could log
            continue
    return plugins

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
            sys.modules[f"modpmv_plugin_{name}"] = mod
            spec.loader.exec_module(mod)  # type: ignore
            # collect plugin classes
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
    """
    Returns structure:
      {
        "audio": {"plugin_name": PluginClassOrFactory},
        "visual": {"plugin_name": PluginClassOrFactory}
      }
    """
    audio = {}
    visual = {}
    # entry points
    audio.update(_load_from_entry_points("modpmv.plugins.audio"))
    visual.update(_load_from_entry_points("modpmv.plugins.visual"))
    # folder fallback
    if plugin_folder:
        folder_audio = os.path.join(plugin_folder, "audio")
        folder_visual = os.path.join(plugin_folder, "visual")
        # try both top-level plugin files and grouped folders
        audio.update(_load_from_folder(os.path.join(plugin_folder, "")))
        audio.update(_load_from_folder(folder_audio))
        visual.update(_load_from_folder(folder_visual))
    return {"audio": audio, "visual": visual}