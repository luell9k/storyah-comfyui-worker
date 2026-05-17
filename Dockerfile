# Storyah's ComfyUI worker image — extends runpod/worker-comfyui with the
# custom nodes we need (Runpod's docs explicitly say custom_nodes MUST be in
# the image, not on the network volume — only the model weights live there).
#
# Build target:  ghcr.io/<your-github>/storyah-comfyui:latest
# Models:        live on a network volume mounted at /runpod-volume/models
# IndexTTS-2 ckpts: symlinked from /runpod-volume/indextts2-ckpts into the
#                   custom_nodes dir at container start (volume → image dir).

FROM runpod/worker-comfyui:5.8.5-base

# Avoid timezone/apt-utils prompts
ENV DEBIAN_FRONTEND=noninteractive

# Wan 2.2 needs no custom node — native ComfyUI ships WanImageToVideo +
# Wan22ImageToVideoLatent (comfy_extras/nodes_wan.py).

# ── IndexTTS-2 custom node (snicolast wrapper) ─────────────────────────────
RUN cd /comfyui/custom_nodes \
 && git clone --depth 1 https://github.com/snicolast/ComfyUI-IndexTTS2 \
 && pip install --no-cache-dir wetext \
 && pip install --no-cache-dir -r ComfyUI-IndexTTS2/requirements.txt

# Pin transformers to 4.x so it stays compatible with the base image's torch
RUN pip install --no-cache-dir "transformers>=4.50,<5"

# ── MuseTalk lip-sync (AIFSH wrapper) ──────────────────────────────────────
# Used as a second-pass refinement after Wan-S2V to tighten mouth motion.
# Heavy deps: mmcv/mmdet/mmpose build can take 15-30 min and is CUDA-sensitive.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 \
 && rm -rf /var/lib/apt/lists/*
RUN cd /comfyui/custom_nodes \
 && git clone --depth 1 https://github.com/AIFSH/ComfyUI-MuseTalk_FSH \
 && pip install --no-cache-dir -r ComfyUI-MuseTalk_FSH/requirements.txt \
 && pip install --no-cache-dir cuda_malloc
RUN pip install --no-cache-dir -U openmim \
 && mim install mmengine \
 && mim install "mmcv>=2.0.1" \
 && mim install "mmdet>=3.1.0" \
 && mim install "mmpose>=1.1.0"

# Storyah custom nodes (audio→images shim so worker-comfyui picks up TTS output)
COPY custom_nodes/ /comfyui/custom_nodes/storyah_custom/

# Wire IndexTTS-2's "checkpoints" dir to the network volume so we don't have
# to bake the 5.5 GB into the image. start.sh creates this symlink at run time
# (volume is only available at run time, not build).
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh
ENTRYPOINT ["/opt/entrypoint.sh"]
