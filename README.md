## Plugins

- Add plugins for custom visual styles and audio sources

ModPMV supports plugins for:
- Visual plugins (render visuals for a given audio/duration/size)
- Audio plugins (transform or generate audio)

Plugin discovery:
1. Preferred: install a plugin package that registers entry points under:
   - `modpmv.plugins.audio`
   - `modpmv.plugins.visual`

   Example (pyproject.toml):
   ```toml
   [project.entry-points."modpmv.plugins.audio"]
   "sample-normalize" = "your_package.plugins:NormalizePlugin"

   [project.entry-points."modpmv.plugins.visual"]
   "sample-solid" = "your_package.plugins:SolidClipPlugin"
   ```

2. Fallback: place Python files in a `plugins/` folder at project root.
   - `plugins/sample_audio.py`
   - `plugins/sample_visual.py`
   The loader will import and detect classes that subclass the base plugin APIs.

How to write a plugin
- Subclass `modpmv.plugins.base.AudioPlugin` or `modpmv.plugins.base.VisualPlugin`.
- Provide `name` and `description` class attributes.
- Implement `process(audio: AudioSegment) -> AudioSegment` for audio plugins.
- Implement `render(audio_path: Optional[str], duration: float, size: (int,int))` and return a moviepy clip for visual plugins.

Loading plugins in code
```python
from modpmv.plugins.loader import discover_plugins

all_plugins = discover_plugins(plugin_folder="plugins")
audio_plugins = all_plugins["audio"]
visual_plugins = all_plugins["visual"]

# instantiate and use
AudioCls = audio_plugins.get("sample-normalize-reverse")
if AudioCls:
    p = AudioCls(config={"reverse": True})
    processed_audio = p.process(input_audio_segment)

VisualCls = visual_plugins.get("sample-solid-visual")
if VisualCls:
    v = VisualCls(config={"color": (255, 0, 0)})
    clip = v.render(audio_path="output/audio.mp3", duration=30.0, size=(1280,720))
    clip.write_videofile("output/out.mp4")
```

Notes and recommendations
- Keep plugins small and dependency-light where possible. If a plugin requires heavy deps, document it and consider packaging as a separate pip package.
- Use entry points for redistributable plugins and the `plugins/` folder for local experimentation.
- For more complex visuals, return a moviepy VideoClip (frame-based) so the core pipeline can concatenate and audio-sync easily.