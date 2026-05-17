"""Storyah custom node: take MuseTalk's silent output video + the original TTS
audio (both as file paths — that's AIFSH's VIDEO/AUDIO convention) and mux
them into one MP4 saved to ComfyUI's output dir, registered under
{"ui": {"images": [...]}} so runpod/worker-comfyui's handler picks it up.

Bridges AIFSH/ComfyUI-MuseTalk_FSH (path-based) with worker-comfyui's
image-output scanning.
"""

import os
import folder_paths


class StoryahMuseTalkSave:
    """Mux MuseTalk's silent MP4 with the original audio, save as MP4, emit ui.images."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO",),
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "storyah_musetalk"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Storyah"

    def save(self, video, audio, filename_prefix):
        # `video` and `audio` arrive as STRING file paths (AIFSH convention).
        video_path = str(video)
        audio_path = str(audio)

        output_dir = folder_paths.get_output_directory()
        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, output_dir
        )
        os.makedirs(full_output_folder, exist_ok=True)

        file = f"{filename}_{counter:05}_.mp4"
        out_path = os.path.join(full_output_folder, file)

        # Mux via moviepy (already a dep of AIFSH/ComfyUI-MuseTalk_FSH).
        from moviepy.editor import VideoFileClip, AudioFileClip
        with VideoFileClip(video_path) as v, AudioFileClip(audio_path) as a:
            v_with_audio = v.set_audio(a)
            v_with_audio.write_videofile(
                out_path,
                codec="libx264",
                audio_codec="aac",
                logger=None,
                temp_audiofile=os.path.join(full_output_folder, f".{filename}_tmp_audio.m4a"),
                remove_temp=True,
            )

        return {"ui": {"images": [{
            "filename": file,
            "subfolder": subfolder or "",
            "type": "output",
        }]}}


NODE_CLASS_MAPPINGS = {"StoryahMuseTalkSave": StoryahMuseTalkSave}
NODE_DISPLAY_NAME_MAPPINGS = {"StoryahMuseTalkSave": "Storyah MuseTalk Save (mux & emit)"}
