"""Standalone MuseTalk inference runner — runs inside the Python 3.10 side
venv at /opt/musetalk-py310. Called by the ComfyUI bridge node
(custom_nodes/storyah_custom/storyah_musetalk_bridge.py) via subprocess.

Usage:
    python runner.py <video_in.mp4> <audio_in.wav> <video_out.mp4> [batch_size=2]

Output: MuseTalk-refined MP4 written to <video_out.mp4>. Stdout prints
final path on success; non-zero exit on failure.
"""

import os
import sys

AIFSH_DIR = "/opt/musetalk-py310/aifsh"


def main(video_in: str, audio_in: str, video_out: str, batch_size: int = 2):
    if not os.path.isfile(video_in):
        raise FileNotFoundError(f"video_in not found: {video_in}")
    if not os.path.isfile(audio_in):
        raise FileNotFoundError(f"audio_in not found: {audio_in}")

    os.environ.setdefault("FFMPEG_PATH", "/usr/bin")
    sys.path.insert(0, AIFSH_DIR)
    from inference import MuseTalk_INFER

    mt = MuseTalk_INFER(
        bbox_shift=0,
        fps=16,           # match Wan-S2V output framerate
        batch_size=batch_size,
        batch_size_fa=1,
    )
    silent = mt(video_in, audio_in)
    # AIFSH's inference produces a SILENT MP4 (the cmd_combine_audio line is
    # commented out in inference.py). Mux audio in ourselves.
    import subprocess
    out_abs = os.path.abspath(video_out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", silent,
        "-i", audio_in,
        "-c:v", "copy", "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        out_abs,
    ], check=True)
    print(out_abs)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: runner.py <video_in> <audio_in> <video_out> [batch_size]", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3],
         int(sys.argv[4]) if len(sys.argv) > 4 else 2)
