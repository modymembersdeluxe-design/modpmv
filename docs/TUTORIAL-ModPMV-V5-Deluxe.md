# ModPMV V5 Deluxe — Full Tutorial (YTPMV generator)

This tutorial explains how to install, run, and extend ModPMV V5 Deluxe — a production-ready YTPMV generator that turns tracker modules (.it/.xm/.mod) and asset libraries into synchronized audio + visuals using a plugin-driven pipeline and high-performance FFmpeg rendering.

Contents
- What is ModPMV V5 Deluxe
- Quick prerequisites
- Install & environment setup
- FFmpeg / moviepy notes
- Module-tracker adapter (binary .it/.xm/.mod)
- Project layout overview
- Quick GUI walkthrough
- Headless CLI usage
- Rendering modes (moviepy, ffmpeg concat, stream)
- Plugin system (types, how to author)
- Preview, caching & reproducibility
- Render queue & batch workflows
- YTPMV packaging & manifest format
- Diagnostics & troubleshooting
- Performance tips and production recommendations
- Useful commands & examples
- Next steps & recommended enhancements

---

What is ModPMV V5 Deluxe
- A toolkit + GUI + CLI to generate YTPMV-style videos from tracker patterns and asset folders.
- V5 adds streaming ffmpeg encode (low memory), tighter exporter with timestamped timeline, and robust module-tracker adapter for parsing modules.
- Extensible via plugins: audio transforms, visual generators, layered effects and exporters.

---

Quick prerequisites
- Python 3.9+ (64-bit recommended)
- FFmpeg binary on PATH (required for stream/ffmpeg modes)
- Optional: module-tracker binding for binary tracker parsing (importable as `module_tracker` / `moduletracker`)
- Recommended: virtual environment

---

Install & environment setup

1) Create and activate venv
- Windows PowerShell:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
- Windows CMD:
  ```cmd
  python -m venv .venv
  .\.venv\Scripts\activate.bat
  ```
- macOS / Linux:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

2) Install dependencies
```bash
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
```

3) Optional: install module-tracker binding if you want binary module parsing
```bash
pip install module-tracker
```
(Replace package name with the binding your environment provides. If you don't have one, ModPMV falls back to a text `.mod` parser.)

4) Install FFmpeg
- macOS: `brew install ffmpeg` (or download static builds)
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: download a static build and add `...\ffmpeg\bin` to PATH
- Or use imageio-ffmpeg: `pip install imageio-ffmpeg` (ModPMV will try imageio-ffmpeg if system ffmpeg not found)

---

FFmpeg and moviepy notes
- MoviePy uses FFmpeg under the hood. For large projects prefer `mode=stream` (ffmpeg stdin) or `mode=ffmpeg` (concat) to avoid memory pressure.
- If ffmpeg is missing, you can still use `moviepy` writes, but large HD renders may fail or be slow.
- For Windows, make sure MSVC redistributable is installed if you get DLL errors for Qt or other binary wheels.

---

Module-tracker adapter (binary .it/.xm/.mod)
- ModPMV expects a "module-tracker" compatible binding; adapter attempts several constructor patterns.
- If adapter fails, the parser falls back to text parsing and writes diagnostics to `output/adapter_diag_*.txt`.
- To debug a binding:
  - Run the diagnostics helper:
    ```python
    from modpmv.openmpt_adapter import run_diagnostics
    data = open("path/to/module.it","rb").read()
    print(run_diagnostics(data))
    ```
  - Paste diagnostics if you want the adapter tailored; adapter can be extended to call the binding's actual constructor.

Text-format .mod
- If you don't have a binding, use simple text modules (example format in `examples/examples.mod`) where tokens like `SAMPLE:kick` map to assets.

---

Project layout (important)
- modpmv/
  - openmpt_adapter.py — binding adapter + diagnostics
  - mod_parser.py — parses binary or text modules and normalizes module_data
  - assets.py — asset resolution helpers
  - audio_renderer.py — maps patterns -> pydub timeline
  - video_renderer.py — per-channel compositing + write modes (moviepy, ffmpeg concat, stream)
  - ytpmv_exporter.py — package exporter; writes `manifest.json` (timestamped timeline)
  - plugins/ — base classes, loader, examples
  - gui.py — Qt GUI with background worker
  - cli.py — headless runner
  - queue.py, cache.py, utils.py — support utilities
- examples/plugins — sample plugins
- requirements.txt, pyproject.toml
- docs/, tests/

---

Quick GUI walkthrough
1) Run GUI:
```bash
python -m modpmv.gui
```
2) Load a module:
- Text `.mod` or binary `.it/.xm/.mod` (if binding present)
3) Select asset folders:
- Audio: `assets/audio_samples`
- Video: `assets/video_samples`
- Images: `assets/images` (fallback)
4) Select plugins (audio & visual)
5) Edit plugin config (JSON) or use presets
6) Preview (low-res cached)
7) Render & Export (threaded worker); optionally add to queue

The GUI shows progress and saves a YTPMV package to `output/`.

---

Headless CLI usage
- Basic:
```bash
python -m modpmv.cli --module examples/examples.mod --out output
```
- With plugins and stream mode:
```bash
python -m modpmv.cli --module examples/examples.mod \
  --audio-plugin beat-slicer --visual-plugin waveform-visual \
  --mode stream --out output
```
CLI options: `--module`, `--audio-assets`, `--video-assets`, `--image-assets`, `--audio-plugin`, `--visual-plugin`, `--mode` (moviepy|ffmpeg|stream), `--out`.

---

Rendering modes explained

1) moviepy (default)
- Easier, composes clips in memory with moviepy.
- Good for previews and short renders.
- May hit memory limits for long HD outputs.

2) ffmpeg (concat)
- Writes per-row MP4 segments, concatenates them with `ffmpeg -f concat`.
- More memory efficient, faster for long timelines.
- Requires consistent codecs / resolution, but code includes re-encoding fallback.

3) stream (ffmpeg stdin)
- Streams raw frames to ffmpeg stdin; ffmpeg encodes on-the-fly (recommended for longest, HD jobs).
- Requires ffmpeg binary (or imageio-ffmpeg).
- Best performance + low memory when combined with a frame producer worker pool.

Choosing:
- Prototype → moviepy
- Medium-length → ffmpeg
- Long/HD/batch → stream

---

Plugin system (authoring & discovery)

Types:
- AudioPlugin / AudioEffectPlugin
  - method: `process(audio: AudioSegment) -> AudioSegment`
  - optional: `preview(audio, preview_ms)`
- VisualPlugin
  - method: `render(audio_path, duration, size) -> moviepy.VideoClip`
  - optional: `preview(...)`
- VisualEffectPlugin
  - method: `apply(clip) -> clip` — for per-row chainable effects
- LayeredVisualPlugin
  - method: `create_layers(audio_path, duration, size) -> list[{"clip", "z", "opacity", "blend"}]`

Metadata:
- `name`, `description`, `tags`, `version`, `license`, `deps`

Discovery:
- Local `plugins/` folder or `examples/plugins/`
- setuptools entry points (optional)

Example visual plugin skeleton:
```python
from modpmv.plugins.base import VisualPlugin
class WaveformVisual(VisualPlugin):
    name = "waveform-visual"
    def render(self, audio_path, duration, size):
        # return a moviepy VideoClip
        ...
```

Authoring tips:
- Keep plugin imports lazy (inside methods) to avoid heavy startup cost.
- Implement a light `preview()` for GUI.
- Use `seed` in config for reproducible randomness.

---

Preview, caching & reproducibility
- Previews cached under `.modpmv_cache/` keyed by job hash.
- Deterministic runs: include `seed` in plugin config and use it in visuals/audio transforms.
- Keep preview resolution & fps low (e.g., 640x360 @ 15–24fps) for responsiveness.

---

Render queue & batch workflows
- GUI adds jobs to `.modpmv_jobs/` (JSON manifests).
- Use CLI or a worker process to consume jobs for unattended batch processing.
- Jobs contain module path, assets, plugin choices, config, mode, and out path.

Example job manifest:
```json
{
  "module": "examples/examples.mod",
  "audio_assets": "assets/audio_samples",
  "video_assets": "assets/video_samples",
  "image_assets": "assets/images",
  "audio_plugin": "beat-slicer",
  "visual_plugin": "waveform-visual",
  "plugin_config": {"seed": 42},
  "mode": "stream",
  "out": "output/job1"
}
```

---

YTPMV packaging & manifest format
- Exporter copies:
  - Generated audio and video into the package
  - Used video sample files into `video_clips/` (best-effort)
  - Writes `manifest.json` with:
    - module_title, audio, video, copied_video_clips
    - order array, patterns_count
    - `timeline`: list of `{start, duration, pattern_index, row_index, used_files}` — precise mapping for YTPMV editing

Pass renderer `timeline` to exporter:
```python
out_video, used_files, timeline = render_video_from_module_data(...)
manifest = export_ytpmv_package(module_data, out_audio, out_video, used_files, timeline, out_pkg)
```

---

Diagnostics & troubleshooting

- Adapter failures:
  - The parser writes diagnostics into `output/adapter_diag_*.txt` when the module-tracker adapter cannot construct a module wrapper.
  - Run `run_diagnostics(data)` in REPL for verbose output and paste here to extend adapter.

- Qt / PyQt errors:
  - Install PyQt6 or PySide6 into the same venv.
  - On Windows, install MSVC redistributable.

- moviepy / ffmpeg errors:
  - Ensure ffmpeg is on PATH (or `pip install imageio-ffmpeg`) and accessible.
  - For ffmpeg concat issues, pre-encode video samples to consistent codecs/resolutions.

- Memory / performance:
  - Use `mode=stream` for long HD jobs.
  - Use cache for decoded audio when re-rendering many times.

---

Performance tips & production recommendations

- Convert frequently used samples to WAV to avoid on-the-fly decoding overhead.
- Pre-normalize sample video clips to H.264/MP4 with same resolution and frame rate for reliable concat.
- Use `stream` mode with a worker pool that generates frames in parallel and pipes to ffmpeg for maximum throughput.
- For very heavy visual effects, offload per-frame processing to numba/Cython/C++ or GPU libraries.
- Preserve deterministic seeds in plugin configs (seed + plugin version) so results can be reproduced.

---

Useful commands & examples

Activate venv:
```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

Install requirements:
```bash
pip install -r requirements.txt
```

Run GUI:
```bash
python -m modpmv.gui
```

Render headless (stream mode):
```bash
python -m modpmv.cli --module examples/examples.mod --mode stream --out output
```

Run adapter diagnostics:
```bash
python - <<'PY'
from modpmv.openmpt_adapter import run_diagnostics
data = open("examples/example.it","rb").read()
print(run_diagnostics(data))
PY
```

Run tests:
```bash
pytest -q
```

---

Next steps I can implement for you
- Patch GUI to fully support `mode=stream` and to pass renderer timeline into exporter (so the manifest is complete).
- Add a `modpmv.inspect-binding` CLI to print available binding attributes and docstrings to help adapter tuning.
- Implement a streaming worker pool that produces frames in parallel for `stream` mode.
- Auto-generate a form-based plugin config UI from plugin metadata instead of raw JSON.
- Provide example `.it/.xm` module samples for adapter testing.

Tell me which follow-up you want (GUI wiring for stream + exporter manifest; inspect-binding CLI; streaming worker pool; or form-based plugin editor) and I will produce the exact files/patches next.