"""Storyah ComfyUI custom node: refine a Video's lip-sync using MuseTalk,
which lives in a separate Python 3.10 venv at /opt/musetalk-py310.

This node runs in ComfyUI's main Python 3.12 interpreter. It writes the
input Video + Audio to /tmp, shells out to the Py3.10 runner, then loads
the refined MP4 back as a Video object so downstream nodes (Storyah Save
Video) can save it.

The "auto-switch" of Python versions is invisible to the workflow author:
they wire `video → bridge → save` and the interpreter swap happens
inside .execute().
"""

import os
import subprocess
import tempfile
import uuid


PY310 = "/opt/musetalk-py310/bin/python"
RUNNER = "/opt/musetalk-py310/runner.py"


def _save_audio_wav(audio, path):
    """Write a ComfyUI AUDIO dict ({waveform, sample_rate}) to WAV via soundfile."""
    import soundfile as sf
    import torch
    wav = audio["waveform"]
    sr = int(audio.get("sample_rate", 22050))
    if hasattr(wav, "cpu"):
        wav = wav.cpu().numpy()
    # ComfyUI AUDIO is shaped (B, C, N) — take first batch, transpose to (N, C)
    if wav.ndim == 3:
        wav = wav[0]
    sf.write(path, wav.T, sr, subtype="PCM_16", format="WAV")


class StoryahMuseTalkBridge:
    """Run MuseTalk lip-sync refinement in the side Python 3.10 venv."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO",),
                "audio": ("AUDIO",),
            },
            "optional": {
                "batch_size": ("INT", {"default": 2, "min": 1, "max": 16}),
                "fallback_on_error": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "refine"
    CATEGORY = "Storyah"

    def refine(self, video, audio, batch_size=2, fallback_on_error=True):
        if not os.path.isfile(PY310) or not os.path.isfile(RUNNER):
            if fallback_on_error:
                print("StoryahMuseTalkBridge: py310 runtime missing, passing input video through")
                return (video,)
            raise RuntimeError(f"Py3.10 runtime missing: {PY310} / {RUNNER}")

        tmpdir = tempfile.mkdtemp(prefix=f"mtb_{uuid.uuid4().hex[:8]}_")
        try:
            video_in = os.path.join(tmpdir, "in.mp4")
            audio_in = os.path.join(tmpdir, "in.wav")
            video_out = os.path.join(tmpdir, "out.mp4")

            # Write input video (without re-muxing audio; MuseTalk takes audio
            # separately). Use ComfyUI's stock container enum.
            from comfy_api.latest import Types
            video.save_to(video_in, format=Types.VideoContainer.MP4, codec="auto")
            _save_audio_wav(audio, audio_in)

            try:
                subprocess.run(
                    [PY310, RUNNER, video_in, audio_in, video_out, str(batch_size)],
                    check=True,
                    timeout=900,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                if fallback_on_error:
                    print(f"StoryahMuseTalkBridge: subprocess failed ({e!r}); passing input through")
                    return (video,)
                raise

            if not os.path.isfile(video_out):
                if fallback_on_error:
                    print("StoryahMuseTalkBridge: runner produced no output; passing input through")
                    return (video,)
                raise RuntimeError("runner exited 0 but no output file")

            # Load the refined MP4 back as a Video object via the same loader
            # ComfyUI's stock LoadVideo uses.
            from comfy_api.latest._input_impl.video_types import VideoFromFile
            refined = VideoFromFile(video_out)
            return (refined,)
        finally:
            # Leave the temp dir for one job's debugging window; OS will clean
            # eventually. Worker is ephemeral anyway.
            pass


NODE_CLASS_MAPPINGS = {"StoryahMuseTalkBridge": StoryahMuseTalkBridge}
NODE_DISPLAY_NAME_MAPPINGS = {"StoryahMuseTalkBridge": "Storyah MuseTalk Refine (py3.10 bridge)"}
