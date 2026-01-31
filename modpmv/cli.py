"""
Simple CLI for headless generation and batch jobs.
"""
import argparse
import os
from modpmv.mod_parser import parse
from modpmv.audio_renderer import render_audio_from_module_data, apply_audio_plugins, export_audio_segment
from modpmv.video_renderer import render_video_from_module_data
from modpmv.ytpmv_exporter import export_ytpmv_package
from modpmv.plugins.loader import discover_plugins

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--module", required=True, help="Path to .mod/.xm/.it or text .mod")
    p.add_argument("--audio-assets", default="assets/audio_samples")
    p.add_argument("--video-assets", default="assets/video_samples")
    p.add_argument("--image-assets", default="assets/images")
    p.add_argument("--out", default="output")
    p.add_argument("--audio-plugin", default=None)
    p.add_argument("--visual-plugin", default=None)
    p.add_argument("--mode", default="moviepy", choices=("moviepy","ffmpeg"))
    args = p.parse_args()

    module_data = parse(args.module)
    os.makedirs(args.out, exist_ok=True)
    print("Rendering audio...")
    audio = render_audio_from_module_data(module_data, [args.audio_assets])
    # optional audio plugin
    if args.audio_plugin:
        avail = discover_plugins().get("audio", {})
        cls = avail.get(args.audio_plugin)
        if cls:
            audio = apply_audio_plugins(audio, [cls()])
    out_audio = os.path.join(args.out, f"{module_data.get('title')}_track.mp3")
    export_audio_segment(audio, out_audio)
    print("Rendering video...")
    visual_plugins = []
    if args.visual_plugin:
        availv = discover_plugins().get("visual", {})
        cls = availv.get(args.visual_plugin)
        if cls:
            visual_plugins.append(cls())
    out_video = os.path.join(args.out, f"{module_data.get('title')}_video.mp4")
    render_video_from_module_data(module_data, out_audio, [args.video_assets], [args.image_assets], out_video, mode=args.mode, visual_plugins=visual_plugins)
    print("Exporting package...")
    used_videos = []  # for CLI we don't track used list precisely here
    manifest = export_ytpmv_package(module_data, out_audio, out_video, used_videos, os.path.join(args.out, f"{module_data.get('title')}_ytpmv_pkg"))
    print("Done. Manifest:", manifest)

if __name__ == "__main__":
    main()