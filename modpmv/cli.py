"""
Simple CLI for headless batch generation.
"""
import argparse
from modpmv.audio_renderer import random_clip_from_folder, assemble_track, export_track
from modpmv.video_renderer import render_video_for_audio
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="output/demo_track.mp3")
    parser.add_argument("--audio-assets", default="assets/audio")
    parser.add_argument("--img-assets", default="assets/images")
    args = parser.parse_args()

    clips = [random_clip_from_folder(args.audio_assets, length_ms=1500) for _ in range(8)]
    track = assemble_track(clips)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    export_track(track, args.out)
    render_video_for_audio(args.out, args.img_assets, args.out.replace(".mp3", ".mp4"))

if __name__ == "__main__":
    main()