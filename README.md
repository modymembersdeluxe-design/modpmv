# ModPMV V4 Deluxe — Overview & Quickstart

ModPMV V4 Deluxe is a production-orientated edition of ModPMV V4 featuring:
- Robust tracker (.it/.xm/.mod) parsing support (OpenMPT adapters incl. omp4py)
- Plugin-driven pipeline: Audio, Visual, Layer, Effect plugins with metadata and preview hooks
- Per-channel (1–32) mapping from tracker patterns -> video samples / image fallbacks
- FFmpeg-backed rendering pipeline (concat/encode path) and moviepy fallback
- Threaded GUI worker, render queue, deterministic random seeds & caching
- Example plugins, presets, tests and CI workflow

Quick start
1. Create virtualenv and activate:
   python -m venv .venv
   .\.venv\Scripts\activate    # Windows
   source .venv/bin/activate   # macOS/Linux
2. Install dependencies:
   pip install -r requirements.txt
3. Install FFmpeg and add to PATH (or set IMAGEIO_FFMPEG_BINARY)
4. Run GUI:
   python -m modpmv.gui

Project layout (important)
- modpmv/
  - core: mod_parser.py, openmpt_adapter.py, audio_renderer.py, video_renderer.py, ytpmv_exporter.py
  - plugins: base.py, loader.py, marketplace.py
  - gui.py (threaded)
  - cli.py
  - queue.py
  - cache.py, utils.py, assets.py
- examples/plugins/ (sample plugins + presets)
- docs/, tests/, .github/workflows/

See docs/TUTORIAL-ModPMV.md for full usage and tips.