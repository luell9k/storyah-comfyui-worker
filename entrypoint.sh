#!/bin/bash
# Storyah worker entrypoint: symlink network-volume content into ComfyUI's
# expected paths, then defer to the upstream runpod/worker-comfyui handler.
set -e

# IndexTTS-2 expects its model bundle at custom_nodes/ComfyUI-IndexTTS2/checkpoints
# We keep the bundle on the network volume (mounted at /runpod-volume) and
# symlink it in. Idempotent.
IDX_CKPT_SRC=/runpod-volume/indextts2-ckpts
IDX_CKPT_DST=/comfyui/custom_nodes/ComfyUI-IndexTTS2/checkpoints
if [ -d "$IDX_CKPT_SRC" ] && [ ! -e "$IDX_CKPT_DST" ]; then
    ln -s "$IDX_CKPT_SRC" "$IDX_CKPT_DST"
fi

# Defer to the base image's original entrypoint
exec /start.sh "$@"
