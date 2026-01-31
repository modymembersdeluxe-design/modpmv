# ModPMV — V3 (Overview)

ModPMV V3 is a major update to the ModPMV toolkit: a Python GUI + pipeline for automatic generation of YTPMV-style audio + visuals from tracker modules and asset folders. V3 emphasizes:

- Robust binary tracker support (.it, .xm, .mod) via OpenMPT adapter (optional binding)
- Full plugin manifest: Audio/Visual/Effect/Layered plugins with tags, metadata and preview helpers
- Per-channel (1–32) mapping of tracker patterns → video samples / image fallbacks / generated visuals
- GUI improvements: Qt binding compatibility (PyQt6 / PySide6 / PyQt5 / PySide2 fallback), plugin config editor (JSON + simple form presets), live preview, render queue, and caching
- Render performance options: moviepy path (easy) and ffmpeg-pipelined path (faster/stable for long renders)
- YTPMV exporter that packages used assets + manifest and precise timestamp mapping
- Enhanced docs, changelog and tests scaffold

This README contains quick start steps, V3 highlights, project layout, and links to tutorials.

Quick start (short)
1. Create & activate a virtualenv:
   python -m venv .venv
   .\.venv\Scripts\activate
2. Install runtime deps:
   pip install -r requirements.txt
3. Install ffmpeg (add to PATH) or install imageio-ffmpeg.
4. Copy or prepare asset folders:
   - assets/audio_samples/
   - assets/video_samples/
   - assets/images/
5. Run GUI:
   python -m modpmv.gui
6. Use the GUI to load a tracker module (.it/.xm/.mod) or text .mod, pick assets and plugin presets, run Preview then Full Export.

Notes
- OpenMPT parsing requires an external binding (e.g., `pyopenmpt` or `openmpt`). If not installed, the app falls back to a text-format parser for prototyping.
- On Windows, use the GUI compatibility fallback if PyQt6 import fails (the GUI tries PySide6 / PyQt5 / PySide2).
- For production rendering of many hours or HD assets, prefer enabling the ffmpeg pipeline and running renders headless via the CLI with a render queue.

Project layout (important files)
- pyproject.toml, requirements.txt
- modpmv/
  - __init__.py
  - mod_parser.py
  - openmpt_adapter.py
  - assets.py
  - audio_renderer.py
  - video_renderer.py
  - plugins/
    - base.py
    - loader.py
  - gui.py
  - cli.py
  - ytpmv_exporter.py
  - cache.py
  - utils.py
- examples/
  - plugins/ (example plugin implementations)
  - examples.mod (sample text module)
- docs/
  - TUTORIAL-ModPMV.md
  - RUNNING-MODPMV-WINDOWS.md
- tests/ (smoke tests scaffold)

Changelog (high level)
- V3: Add OpenMPT-backed parsing, channel-aware video rendering, plugin manifest & preview, GUI improvements, ffmpeg pipeline option, caching, improved exporter with timestamp mapping.

If you'd like, I can:
- Wire an advanced per-channel mapping UI in the GUI (drag-drop channel → asset mapping).
- Implement two polished example plugins: WaveformVisual (GPU-ready path) and BeatSlicerAudio with unit tests.
- Add GitHub Actions CI (install ffmpeg via apt on runners, run smoke tests).

Read the docs in `docs/` for full installation and platform-dependent notes.