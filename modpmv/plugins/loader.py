"""
Plugin discovery & manifest for ModPMV Deluxe. Supports:
- setuptools entry points
- local plugins/ folder (audio/, visual/) and examples/plugins
- Marketplace metadata (license, deps)
"""
import os, sys, importlib.util
from importlib.metadata import entry_points
from typing import Dict, Any, List, Optional
from .base import AudioPlugin, VisualPlugin

def _from_entry_points(group: str) -> Dict[str, Any]:
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

def _from_folder(folder: str) -> Dict[str, Any]:
    plugins = {}
    if not os.path.isdir(folder):
        return plugins
    sys.path.insert(0, folder)
    for fn in os.listdir(folder):
        if not fn.endswith(".py") or fn.startswith("_"): continue
        path=os.path.join(folder, fn)
        modname=os.path.splitext(fn)[0]
        try:
            spec=importlib.util.spec_from_file_location(modname, path)
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            for attr in dir(mod):
                obj=getattr(mod, attr)
                try:
                    if isinstance(obj, type) and issubclass(obj, (AudioPlugin, VisualPlugin)) and obj not in (AudioPlugin, VisualPlugin):
                        plugins[getattr(obj, "name", f"{modname}.{attr}")] = obj
                except Exception:
                    continue
        except Exception:
            continue
    try: sys.path.pop(0)
    except Exception: pass
    return plugins

def discover_plugins(plugin_folder: Optional[str] = "plugins") -> Dict[str, Dict[str, Any]]:
    audio={}; visual={}
    audio.update(_from_entry_points("modpmv.plugins.audio"))
    visual.update(_from_entry_points("modpmv.plugins.visual"))
    if plugin_folder:
        audio.update(_from_folder(os.path.join(plugin_folder,"audio")))
        visual.update(_from_folder(os.path.join(plugin_folder,"visual")))
        audio.update(_from_folder(plugin_folder))
        visual.update(_from_folder(plugin_folder))
    # include shipped examples by default
    audio.update(_from_folder(os.path.join("examples","plugins")))
    visual.update(_from_folder(os.path.join("examples","plugins")))
    return {"audio":audio,"visual":visual}

def list_plugins_manifest(plugin_folder: Optional[str] = "plugins") -> List[Dict[str, Any]]:
    discovered = discover_plugins(plugin_folder)
    manifest=[]
    for ptype in ("audio","visual"):
        for name, cls in discovered.get(ptype, {}).items():
            try:
                manifest.append({
                    "name": getattr(cls, "name", name),
                    "type": ptype,
                    "description": getattr(cls, "description","") or "",
                    "tags": getattr(cls, "tags", []) or [],
                    "version": getattr(cls, "version","0.0.1"),
                    "license": getattr(cls, "license",""),
                    "deps": getattr(cls, "deps", []),
                    "class": cls
                })
            except Exception:
                continue
    manifest.sort(key=lambda m:(m["type"], m["name"]))
    return manifest