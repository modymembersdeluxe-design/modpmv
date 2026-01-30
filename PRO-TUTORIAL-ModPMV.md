# ModPMV — Pro Tutorial (Advanced guide)

This pro tutorial covers installation, architecture, advanced workflows, plugin development patterns, performance tuning, testing & CI, packaging, and production tips for ModPMV V2 — the Python GUI + pipeline for generating YTPMV-style audio + visuals.

Contents
- Goals & expectations
- Quick install & tools
- Project architecture (modules & responsibilities)
- Quickstart: GUI and headless pipeline
- Advanced usage: batch, presets, and pipelines
- Plugin development — best practices and examples
  - Audio plugin: beat-slicer (example)
  - Visual plugin: waveform visual (example)
  - VisualEffect & Layered plugin patterns
  - Keyframing & graph usage
- Asset management & sample naming strategy
- Performance & rendering best practices
- Testing, CI, and reproducible builds
- Packaging and distribution
- Troubleshooting & FAQ
- Next steps & roadmap

---

Goals & expectations
- This tutorial assumes familiarity with Python, virtualenv, audio/video tooling (ffmpeg), and basic GUI concepts.
- ModPMV aims to be an extensible pipeline: parse module-like inputs, map samples to audio/video assets, apply plugins, render audio and visuals, and export a package for YTPMV editors.
- The “Pro” workflow focuses on reproducibility, performance, extendability, and production-safe pipelines.

Quick install & tools
1. Clone your ModPMV repository and create a venv:
   - python -m venv .venv
   - source .venv/bin/activate  (macOS/Linux) or .venv\Scripts\activate (Windows)
2. Install dependencies:
   - pip install -r requirements.txt
3. Install/verify ffmpeg on PATH:
   - ffmpeg -version
4. Optional useful tools:
   - ffprobe (part of ffmpeg), sox (audio transformations), OpenCV (advanced visuals), GPU-accelerated encoders if available.

Project architecture (high level)
- modpmv/mod_parser.py
  - Parse .mod-like input (text starter). Extend or swap for binary formats (ProTracker/XM/IT).
- modpmv/assets.py
  - Locate and resolve audio/video/image files by name or path.
- modpmv/audio_renderer.py
  - Map patterns → audio timeline (row duration) → produce a pydub AudioSegment.
  - Supports chaining audio plugins (AudioPlugin/AudioEffectPlugin).
- modpmv/video_renderer.py
  - Map pattern events → per-row visuals, assemble timeline using moviepy.
  - Supports per-row visual effects and plugin-driven renderers (VisualPlugin, VisualEffectPlugin, LayeredVisualPlugin).
- modpmv/plugins/*
  - Base classes & loader. Plugins register via entry points or a plugins/ folder.
- modpmv/ytpmv_exporter.py
  - Gather used assets, copy into a package, emit manifest JSON.
- modpmv/gui.py
  - PyQt advanced UI for selecting module, assets, plugins, preview & export.

Quickstart: GUI & headless
- GUI:
  - python -m modpmv.gui
  - Load a .mod text file (examples/examples.mod), select asset folders, choose optional plugins, set plugin JSON config, and Render & Export.
- Headless (CLI pattern):
  - Use modpmv.cli or write a short script that:
    1. parse_mod_text(...)
    2. render_audio_from_module(...)
    3. apply_audio_plugins(...)
    4. export_audio_segment(...)
    5. render_video_from_module(..., visual_plugins=[...])
    6. export_ytpmv_package(...)

Advanced usage: batch runs & presets
- Presets
  - Save plugin configs as JSON presets under `presets/` (e.g., `presets/waveform_bold.json`). GUI can load presets into the JSON editor.
- Batch script pattern
  - Use a job queue (CSV/JSON manifest) that lists .mod file + asset folders + plugin presets.
  - Run a worker process pool to render multiple projects in parallel (respecting CPU/RAM limits).
- Deterministic randomization
  - If random selection is used (random image, clip), seed RNG per project using a stable seed derived from module title + timestamp to reproduce runs.

Plugin development — best practices
- Keep plugin responsibilities single-purpose and lightweight.
- Declare metadata: `name`, `description`, `tags` (helps GUI filter by capability).
- Make plugin config JSON-serializable (simple types — numbers, strings, lists).
- Prefer pure-Python or small dependencies; document heavy dependencies.
- Provide a `preview(self, audio_path, duration, size, out_preview_path)` helper for GUI preview generation (1–3 seconds).
- Gracefully handle errors (raise meaningful exceptions with context).

Plugin development patterns
- AudioPlugin.process(AudioSegment) -> AudioSegment
  - Non-destructive: default to returning input if no config applied.
- VisualPlugin.render(audio_path, duration, size) -> moviepy.VideoClip
  - If plugin uses external files, accept absolute paths or asset-folder lookup.
- VisualEffectPlugin.apply(clip) -> clip
  - Chainable: multiple effects can be applied in sequence.
- LayeredVisualPlugin.create_layers(...) -> list[dict]
  - Return layers with z-index & opacity for robust compositing.

Example: Beat-slicer audio plugin (concept)
- Detect beats using librosa on the input audio
- For each beat segment, slice and optionally rearrange, repeat, pitch-shift, or apply gate effects
- Useful config keys: detect_hop_length, energy_threshold, slice_mode, repeat_density, time_stretch_range

File: examples/plugins/beat_slicer_audio.py
```python
from modpmv.plugins.base import AudioEffectPlugin
import librosa
from pydub import AudioSegment
import numpy as np
import io

class BeatSlicer(AudioEffectPlugin):
    name = "beat-slicer"
    description = "Detect beats and slice/rearrange segments"
    tags = ["audio-effect","beat","slice"]

    def process(self, audio: AudioSegment) -> AudioSegment:
        # Convert to numpy float waveform for librosa
        sr = int(self.config.get("sr", 22050))
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        # pydub stores interleaved samples for stereo — handle channels
        channels = audio.channels
        if channels > 1:
            samples = samples.reshape((-1, channels)).mean(axis=1)
        samples /= np.iinfo(audio.array_type).max
        # resample if needed
        # write out to librosa pipeline
        y = samples
        # detect beats
        try:
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)
        except Exception:
            return audio
        # simple slice & shuffle mode demo
        segments = []
        for i in range(len(beat_times)-1):
            s = int(beat_times[i]*1000)
            e = int(beat_times[i+1]*1000)
            segments.append(audio[s:e])
        # rearrange by random seed
        import random
        random.seed(self.config.get("seed", 0))
        random.shuffle(segments)
        out = segments[0] if segments else AudioSegment.silent(1000)
        for seg in segments[1:]:
            out = out.append(seg, crossfade=0)
        return out
```

Example: Waveform visual plugin (concept)
- Render waveform frames using numpy -> matplotlib/agg or cairo
- For speed, prefer rendering as a small canvas and upscale, or use ffmpeg filters to draw waveforms
- Use KeyframeGraph to animate color/zoom parameters across duration

File: examples/plugins/waveform_visual.py
```python
from modpmv.plugins.base import VisualPlugin, KeyframeGraph
from moviepy.editor import VideoClip, AudioFileClip
import numpy as np
import matplotlib.pyplot as plt
import io
from PIL import Image

class WaveformVisual(VisualPlugin):
    name = "waveform-visual"
    description = "Render animated waveform from audio"
    tags = ["waveform","audio-reactive","layer"]

    def render(self, audio_path, duration, size):
        # Precompute a downsampled waveform envelope
        a = AudioFileClip(audio_path)
        sr = int(self.config.get("sr", 22050))
        # Extract samples via ffmpeg or use librosa externally for more precision
        # For demo: sample amplitude envelope using moviepy's to_soundarray (may be large)
        arr = a.to_soundarray(fps=sr)
        mono = arr.mean(axis=1)
        # downsample to frame count
        frame_count = int(self.config.get("resolution", 1024))
        window = max(1, len(mono)//frame_count)
        envelope = [np.abs(mono[i*window:(i+1)*window]).mean() for i in range(frame_count)]
        maxenv = max(envelope) or 1.0
        envelope = [v/maxenv for v in envelope]

        def make_frame(t):
            # map time to position in envelope
            pos = min(int((t/duration) * (len(envelope)-1)), len(envelope)-1)
            # create an image using numpy (simple vertical bars)
            W,H = size
            img = np.zeros((H,W,3), dtype=np.uint8) + 10
            # draw bars centered horizontally
            bar_w = max(1, W//len(envelope))
            for i,v in enumerate(envelope):
                h = int(v * (H*0.45))
                x = i * bar_w
                img[H//2-h:H//2+h, x:x+bar_w] = (30, 200, 255)
            return img
        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_fps(self.config.get("fps", 24))
        return clip.set_duration(duration)
```

Keyframing & motion graph usage
- Use KeyframeGraph for parameter interpolation (scale, opacity, rotation)
- Store keyframes as normalized time [0.0..1.0] or absolute seconds; be consistent
- In layered plugins, pass KeyframeGraph instances to layer clip lambdas:
  - layer_clip.set_opacity(lambda t: kg.value(t/duration))

Asset management & sample naming strategy
- Standardize file naming so sample → asset resolution is deterministic:
  - `kick.wav`, `snare.wav`, `vocal_chop_01.wav`, `clip_fire_01.mp4`
- Avoid spaces and special chars, prefer lower-case.
- If module sample declares `path=...`, trust it; else use `find_audio_for_sample` / `find_video_for_sample`.
- Keep a manifest of assets used for each project to allow reproducible packaging.

Performance & rendering best practices
- MoviePy is easy for prototypes but can be slow for HD renders. Options:
  - Lower preview resolution and fps for quick iteration.
  - Use ffmpeg filters or pre-rendered frames if heavy per-frame numpy operations are used.
  - Offload frame generation to multiple worker processes; then pipe frames to ffmpeg.
- Disk I/O:
  - Cache intermediate audio WAV exports to avoid repeated decoding/encoding.
  - Use WAV for internal processing, export compressed formats only for final packaging.
- Parallelism:
  - Render independent jobs (different .mod files) in parallel processes.
  - Within a single render, you can parallelize frame generation per-chunk but ensure ffmpeg accepts streamed input.
- Memory:
  - Avoid holding long video clips in memory; operate on subclips and write segments to disk and concatenate with ffmpeg.

Testing, CI & reproducible builds
- Unit tests:
  - test parser handles expected token variations
  - test audio renderer produces expected durations and channel counts
  - test plugin loader discovers local & entry-point plugins
  - test at least one-second preview render for every plugin (smoke test)
- CI pipeline:
  - Run tests on PRs
  - Build artifacts (wheel) for releases
  - Optional: publish example plugin package to test entry-point discovery
- Reproducibility:
  - Pin dependencies in CI (use constraints.txt)
  - Use deterministic seeds for any randomness in tests
  - Cache ffmpeg binaries & use consistent ffmpeg version across runners

Packaging & distribution
- For the core library: produce a wheel and sdist via pyproject.toml (PEP 621).
- Plugins:
  - Encourage packaging plugins separately with entry points under `modpmv.plugins.audio` / `modpmv.plugins.visual`
  - Example pyproject snippet:
    ```toml
    [project.entry-points."modpmv.plugins.visual"]
    "waveform-visual" = "yourpkg.waveform:WaveformVisual"
    ```
- Distribution:
  - Host core on GitHub, use GitHub Releases for binaries
  - Publish stable plugins to PyPI, document dependencies

Troubleshooting & FAQ
- ffmpeg not found: ensure ffmpeg binary is installed and on PATH.
- Slow renders: reduce fps/resolution; profile using cProfile on Python side; consider moving heavy operations to compiled extensions or ffmpeg filters.
- Plugin import errors: ensure plugin folder is on PYTHONPATH or packaged with entry point. Use logging to capture import-time exceptions.
- Corrupt audio decoding: pre-convert problematic files to WAV using ffmpeg for robustness.

Production pipeline example
1. Author writes .mod text or supplies binary module files.
2. Asset curator ensures audio/video assets present and named.
3. Job manifest (JSON) created with .mod path, asset folders, plugin presets, export path.
4. Worker pool consumes manifests, sets deterministic random seed, runs headless pipeline:
   - parse -> render audio -> apply audio plugins -> export audio
   - render visuals with visual plugins -> export video
   - collect used assets -> export package
5. Post-process: optional quality checks (verify duration matches, check for missing assets), then commit package to archive.

Next steps & roadmap (suggestions)
- Binary .mod parser: implement/adapter for ProTracker/XM/IT to extract samples & pattern timing.
- More example plugins: GPU-accelerated displacement, chroma-key refinement, text-glitch generator, beat-synced image montage.
- Rich GUI: plugin config forms (not raw JSON), preview thumbnails, render queue, plugin marketplace.
- Performance: native extensions for per-frame effects or FFT-based visualization using numba/numba-cuda.

Appendix — Useful snippets & CLI patterns

Run headless single job (example script)
```python
from modpmv.mod_parser import parse_mod_text
from modpmv.audio_renderer import render_audio_from_module, apply_audio_plugins, export_audio_segment
from modpmv.video_renderer import render_video_from_module
from modpmv.ytpmv_exporter import export_ytpmv_package
from modpmv.plugins.loader import discover_plugins

module = parse_mod_text("examples/demo.mod")
audio = render_audio_from_module(module, ["assets/audio_samples"])
# optionally apply audio plugin
plugins = discover_plugins("examples/plugins")
ap = plugins["audio"].get("simple-audio-processor")
if ap:
    audioplug = ap(config={"gain_db":3})
    audio = apply_audio_plugins(audio, [audioplug])
out_audio = "output/demo_track.mp3"
export_audio_segment(audio, out_audio)
out_video = "output/demo_video.mp4"
render_video_from_module(module, out_audio, ["assets/video_samples"], ["assets/images"], out_video, visual_plugins=[])
export_ytpmv_package(module, out_audio, out_video, [], "output/demo_pkg")
```

Final notes
- Start small: prototype with low-res previews, iterate on plugins, then scale.
- Keep plugin APIs stable for third-parties; use semantic versioning for breaking changes.
- Document plugin contracts clearly in README and add CONTRIBUTING.md for plugin authors.

If you want, I can:
- Add a ready-to-run beat-slicer plugin and waveform visual plugin into `examples/plugins/` with tests and a preview command.
- Implement a per-plugin GUI editor (form-based) and preview button in the PyQt GUI.
- Add a sample CI workflow (GitHub Actions) to run smoke tests and build a wheel.

Which of the above should I implement next for your ModPMV V2 repo?