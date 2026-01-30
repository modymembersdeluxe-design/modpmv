# ModPMV V2 — Quick Tutorial

(Short guide to get started)
1. Install dependencies: pip install -r requirements.txt
2. Ensure ffmpeg is on PATH.
3. Place assets:
   - assets/audio_samples/
   - assets/video_samples/
   - assets/images/
4. Create a simple .mod text (see examples/) and open it with the GUI.
5. Select optional plugins from the dropdown (example plugins are read from `examples/plugins`).
6. Enter plugin config JSON if necessary (applies to selected plugins), then Render & Export.

Plugin quick tips
- Audio plugins: must implement `process(AudioSegment) -> AudioSegment`
- Visual plugins: must implement `render(audio_path, duration, size) -> VideoClip`
- VisualEffectPlugin: implement `apply(clip) -> clip`
- LayeredVisualPlugin: implement `create_layers(...) -> list of {clip,z,opacity}`

Next improvements
- Plugin config editor UI for per-plugin configs
- Preview/thumbnail caching for plugin selections
- Real binary .mod parsers (ProTracker/IT/XM) and sample extraction