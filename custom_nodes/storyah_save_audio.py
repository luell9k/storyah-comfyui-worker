"""Storyah custom node: save an AUDIO tensor as a WAV/MP3 file and
register it under {"ui": {"images": [...]}} so runpod/worker-comfyui's
output handler (which only scans node_output["images"]) actually picks
it up.

Drop this file at /comfyui/custom_nodes/storyah_custom/storyah_save_audio.py
inside the worker image. ComfyUI auto-loads NODE_CLASS_MAPPINGS at startup.
"""

import os
import numpy as np
import folder_paths


class StoryahSaveAudio:
    """Drop-in replacement for IndexTTS2SaveAudio that emits under ui.images."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "name": ("STRING", {"default": "tts", "placeholder": "file name prefix"}),
                "format": (["wav"], {"default": "wav"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Storyah"

    def save(self, audio, name, format):
        output_dir = folder_paths.get_output_directory()
        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            f"storyah/{name}", output_dir
        )
        os.makedirs(full_output_folder, exist_ok=True)

        wav = audio["waveform"]
        sr = int(audio.get("sample_rate", 22050))
        if hasattr(wav, "cpu"):
            wav = wav.cpu().numpy()
        wav = np.asarray(wav)
        if wav.ndim != 3:
            raise ValueError("AUDIO input must be shaped (B, C, N)")

        results = []
        for b in range(wav.shape[0]):
            w = wav[b].astype(np.float32)
            file = f"{filename}_{counter:05}_.wav"
            out_path = os.path.join(full_output_folder, file)
            self._save_wav(out_path, w, sr)
            counter += 1
            # Register under "images" so worker-comfyui scans + uploads it.
            results.append({
                "filename": file,
                "subfolder": subfolder or "",
                "type": "output",
            })

        return {"ui": {"images": results}}

    @staticmethod
    def _save_wav(path, data, sr):
        try:
            import soundfile as sf
            sf.write(path, data.T, sr, subtype="PCM_16", format="WAV")
        except Exception:
            import wave
            import contextlib
            pcm16 = (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16)
            with contextlib.closing(wave.open(path, "wb")) as wf:
                wf.setnchannels(int(data.shape[0]))
                wf.setsampwidth(2)
                wf.setframerate(int(sr))
                wf.writeframes(pcm16.T.tobytes())


NODE_CLASS_MAPPINGS = {"StoryahSaveAudio": StoryahSaveAudio}
NODE_DISPLAY_NAME_MAPPINGS = {"StoryahSaveAudio": "Storyah Save Audio (as image)"}
