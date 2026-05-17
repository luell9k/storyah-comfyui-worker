"""Storyah custom node: save a Video (images + audio) as an MP4 and register
it under {"ui": {"images": [...]}} so runpod/worker-comfyui's output handler
(which only scans node_output["images"]) actually picks it up.

Mirrors ComfyUI's stock SaveVideo (comfy_extras/nodes_video.py) — same
video.save_to(...) call — but emits the result under "images" instead of
"videos" so it survives the worker-comfyui round-trip.
"""

import os
import folder_paths


class StoryahSaveVideo:
    """Save a Video object (use with CreateVideo) as MP4, registering under ui.images."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO",),
                "filename_prefix": ("STRING", {"default": "storyah_clip"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Storyah"

    def save(self, video, filename_prefix):
        # video is comfy.comfy_types.node_typing.VIDEO (PyAV-backed)
        width, height = video.get_dimensions()
        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory(), width, height
        )
        os.makedirs(full_output_folder, exist_ok=True)

        # Defer to ComfyUI's container/codec enums so format strings match.
        from comfy_api.latest import Types

        file = f"{filename}_{counter:05}_.mp4"
        out_path = os.path.join(full_output_folder, file)
        video.save_to(out_path, format=Types.VideoContainer.MP4, codec="auto")

        return {"ui": {"images": [{
            "filename": file,
            "subfolder": subfolder or "",
            "type": "output",
        }]}}


NODE_CLASS_MAPPINGS = {"StoryahSaveVideo": StoryahSaveVideo}
NODE_DISPLAY_NAME_MAPPINGS = {"StoryahSaveVideo": "Storyah Save Video (mp4 w/ audio)"}
