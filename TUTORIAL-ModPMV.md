# ModPMV — Quick Tutorial

This tutorial walks through installing ModPMV, creating a quick project, using the GUI and CLI, and writing simple plugins (audio + visual). It's aimed at the starter scaffold in the repository (modpmv/). If you followed the sample scaffold, this will show practical next steps to get working outputs quickly.

> NOTE: This is a tutorial for the work-in-progress ModPMV scaffold. Replace sample assets and sample .mod text files with real module files when available for better results.

---

- Add plugins for custom visual styles and audio sources

---

Table of contents
- Requirements
- Installation
- Project layout recap
- Quickstart: generate a demo (GUI)
- Quickstart: generate a demo (CLI)
- Plugins: discover & use
- Writing a simple Audio plugin
- Writing a simple Visual plugin
- Working with real .mod files
- Performance & debugging tips
- Frequently asked questions
- Next steps & resources

---

Requirements
- Python 3.9+
- FFmpeg installed and on PATH (moviepy relies on ffmpeg)
- Recommended packages (see requirements.txt): PyQt6, pydub, moviepy, librosa, numpy, soundfile

Installation
1. Clone or copy the project scaffold.
2. Create a virtual environment:
   - python -m venv .venv
   - source .venv/bin/activate  (Linux/macOS) or .venv\Scripts\activate (Windows)
3. Install dependencies:
   - pip install -r requirements.txt
   - Ensure ffmpeg is installed (apt/yum/brew/choco or download from ffmpeg.org)

Project layout (recap)
- modpmv/
  - mod_parser.py         # simple demo parser
  - audio_renderer.py     # pydub-based audio assembly
  - video_renderer.py     # moviepy-based visuals
  - plugins/
    - base.py             # plugin interfaces
    - loader.py           # discovery + import
  - gui.py                # PyQt6 demo UI
  - cli.py                # headless generation
- assets/
  - audio/                # put sample audio clips
  - images/               # put sample images for visuals
- output/                 # generated output files

Quickstart — GUI (fast)
1. Populate assets:
   - Put a handful of short audio files (.wav/.mp3) into `assets/audio`.
   - Put some images into `assets/images`.
2. Run the GUI:
   - python -m modpmv.gui
3. In the GUI:
   - Click "Load .mod" to load the demo text .mod (optional).
   - Click "Generate (audio+video)" to create `output/demo_track.mp3` and `output/demo_video.mp4`.
4. Inspect `output/demo_video.mp4` with your media player.

Quickstart — CLI (headless)
1. Populate `assets/audio` and `assets/images` as above.
2. Run:
   - python -m modpmv.cli --out output/demo_track.mp3 --audio-assets assets/audio --img-assets assets/images
3. Output:
   - `output/demo_track.mp3` and `output/demo_track.mp4` will be created.

Plugins — discover & use
ModPMV supports AudioPlugin and VisualPlugin classes. Discovery happens via:
- Entry points (packaged plugins), or
- A project-level `plugins/` folder.

Load available plugins:
```python
from modpmv.plugins.loader import discover_plugins
all_plugins = discover_plugins(plugin_folder="plugins")
print("Audio plugins:", list(all_plugins["audio"]))
print("Visual plugins:", list(all_plugins["visual"]))
```

Instantiate and run:
```python
AudioCls = all_plugins["audio"].get("sample-normalize-reverse")
if AudioCls:
    audio_plugin = AudioCls(config={"reverse": True})
    out_audio = audio_plugin.process(input_audio_segment)
```

Writing a simple Audio plugin (example)
- File: plugins/sample_audio.py
```python
from modpmv.plugins.base import AudioPlugin
from pydub import AudioSegment

class SampleAudioPlugin(AudioPlugin):
    name = "sample-normalize-reverse"
    description = "Normalize audio and optionally reverse"

    def process(self, audio: AudioSegment) -> AudioSegment:
        out = audio.normalize()
        if self.config.get("reverse", False):
            out = out.reverse()
        return out
```
- Save it to `plugins/sample_audio.py`. Run `discover_plugins(plugin_folder="plugins")` to pick it up.

Writing a simple Visual plugin (example)
- File: plugins/sample_visual.py
```python
from modpmv.plugins.base import VisualPlugin
from moviepy.video.VideoClip import ColorClip

class SampleVisualPlugin(VisualPlugin):
    name = "sample-solid-visual"
    description = "Solid-color visual plugin (demo)"

    def render(self, audio_path, duration, size):
        color = tuple(self.config.get("color", (30, 30, 120)))
        clip = ColorClip(size, color=color).set_duration(duration)
        return clip
```
- Save to `plugins/sample_visual.py`. Instantiate and call `.render(audio_path, duration, size)`.

Integrating plugins into the pipeline
- Discover available plugins on startup.
- Choose plugin(s) in the GUI or supply them to the CLI via flags.
- Instantiate with a config dict (plugin-specific).
- For audio pipeline: pass AudioSegment objects through each AudioPlugin.process() in sequence.
- For visuals: ask the selected VisualPlugin to render, then set audio with moviepy (clip.set_audio(AudioFileClip(...))).

Working with real .mod files
- The scaffold's mod_parser.py is a placeholder text parser. Real module formats (ProTracker, FastTracker, etc.) are binary and need a proper parser.
- Options:
  - Provide example .mod files and their expected behavior, and a proper binary parser can be added.
  - Use existing module-handling libraries (if available) or convert modules to WAV samples externally and feed those to ModPMV.
- Suggested workflow:
  1. Parse pattern/order from module to decide which sample clips to select/arrange.
  2. Map tracker samples -> actual sample files in `assets/audio` (or extract embedded PCM if parser supports it).
  3. Use audio plugins to transform slices (time-stretch, pitch-shift, glitch, etc.)
  4. Use visual plugins to create visuals synced to beat or pattern events.

Performance & debugging tips
- MoviePy can be slow for long HD renders. For faster renders:
  - Pre-generate frames with vectorized numpy routines and pipe to ffmpeg.
  - Use lower resolutions / fewer fps for previews.
- For large audio processing, prefer librosa + soundfile for precise control (time-stretch, phase vocoder).
- Use a worker thread or multiprocessing for render jobs in the GUI to avoid freezing the UI.
- Log progress and catch exceptions around external tools (ffmpeg) — moviepy returns helpful errors.

FAQ
Q: My video rendering fails with "ffmpeg not found".
A: Install ffmpeg and ensure it is on your system PATH. On Mac, use brew; on Windows, add ffmpeg bin to PATH.

Q: How do I add a packaged plugin?
A: Create a package that exposes entry points:
```toml
[project.entry-points."modpmv.plugins.audio"]
"my-audio" = "mypkg.plugins:MyAudioPlugin"

[project.entry-points."modpmv.plugins.visual"]
"my-visual" = "mypkg.plugins:MyVisualPlugin"
```
Install the package with pip; discover_plugins() will pick it up.

Troubleshooting
- No audio files found: Ensure `assets/audio` has correct extensions (.wav/.mp3/.ogg).
- Corrupt audio decode errors: Try converting sample files to WAV with ffmpeg and retry.
- GUI freezes during export: Run render in a background thread or process and show progress in the UI.

Next steps & ideas
- Implement a real .mod binary parser using an existing spec or sample files.
- Add more visual plugins: waveform, beat-synced image cuts, text-glitch, chroma-key montages.
- Add audio plugins: beat-slicer, pitch-shifter, gating/glitching, generative synth.
- Add a plugin config editor in GUI and a plugin marketplace via entry points.
- Add unit tests and a CI pipeline to validate plugins and render pipeline.

License & contributions
- Decide a license (MIT recommended for starters).
- Add CONTRIBUTING.md with plugin API stability notes and testing requirements.

If you want, I can:
- Draft CONTRIBUTING.md and plugin API stability guidelines.
- Implement a waveform visual plugin and a beat-slicing audio plugin as examples.
- Replace the placeholder .mod parser with a real parser once you upload representative .mod files.

Enjoy building ModPMV! If you'd like, tell me which example plugin (waveform / beat-slicer / image-montage) to implement next and I will add it.