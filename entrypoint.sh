#!/bin/bash
# Storyah worker entrypoint: wire network-volume model paths into ComfyUI,
# then defer to the upstream runpod/worker-comfyui handler.
set -e

VOL=/runpod-volume

# IndexTTS-2 expects its model bundle at custom_nodes/ComfyUI-IndexTTS2/checkpoints.
# Keep the bundle on the network volume and symlink it in. Idempotent.
IDX_CKPT_SRC="$VOL/indextts2-ckpts"
IDX_CKPT_DST=/comfyui/custom_nodes/ComfyUI-IndexTTS2/checkpoints
if [ -d "$IDX_CKPT_SRC" ] && [ ! -e "$IDX_CKPT_DST" ]; then
    ln -s "$IDX_CKPT_SRC" "$IDX_CKPT_DST"
fi

# Tell ComfyUI to also search /runpod-volume/models for all model categories.
# This file is read at startup; we overwrite each boot so changes to populate
# layout get picked up.
cat > /comfyui/extra_model_paths.yaml <<YAML
runpod_volume:
    base_path: $VOL/models
    is_default: true
    checkpoints: checkpoints
    diffusion_models: diffusion_models
    unet: diffusion_models
    vae: vae
    loras: loras
    text_encoders: text_encoders
    clip: text_encoders
    audio_encoders: audio_encoders
YAML

# Defer to the base image's original entrypoint
exec /start.sh "$@"
