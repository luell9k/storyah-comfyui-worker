# Storyah's ComfyUI worker image — extends runpod/worker-comfyui with the
# custom nodes we need (Runpod's docs explicitly say custom_nodes MUST be in
# the image, not on the network volume — only the model weights live there).
#
# Build target:  ghcr.io/<your-github>/storyah-comfyui:latest
# Models:        live on a network volume mounted at /runpod-volume/models
# IndexTTS-2 ckpts: symlinked from /runpod-volume/indextts2-ckpts into the
#                   custom_nodes dir at container start (volume → image dir).
#
# MuseTalk: incompatible with Python 3.12 — installed into its own Python 3.10
# venv at /opt/musetalk-py310. ComfyUI (Py3.12) calls into it via subprocess
# from custom_nodes/storyah_custom/storyah_musetalk_bridge.py.

FROM runpod/worker-comfyui:5.8.5-base

# Avoid timezone/apt-utils prompts
ENV DEBIAN_FRONTEND=noninteractive

# Wan 2.2 needs no custom node — native ComfyUI ships WanImageToVideo +
# Wan22ImageToVideoLatent (comfy_extras/nodes_wan.py).

# ── System deps (ffmpeg for video mux, libgl for cv2, build-essential for the
#    Python 3.10 venv to compile chumpy/xtcocotools) ─────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libgl1 build-essential software-properties-common ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ── IndexTTS-2 custom node (snicolast wrapper, runs in main Py3.12) ────────
RUN cd /comfyui/custom_nodes \
 && git clone --depth 1 https://github.com/snicolast/ComfyUI-IndexTTS2 \
 && pip install --no-cache-dir wetext \
 && pip install --no-cache-dir -r ComfyUI-IndexTTS2/requirements.txt

# Pin transformers to 4.x in the main Py3.12 env (IndexTTS-2 needs it)
RUN pip install --no-cache-dir "transformers>=4.50,<5"

# ── Python 3.10 side venv for MuseTalk (validated recipe — see
#    docs/musetalk-recipe.md). Deadsnakes PPA ships maintained 3.10 for
#    Ubuntu 24.04. ────────────────────────────────────────────────────────────
RUN add-apt-repository -y ppa:deadsnakes/ppa \
 && apt-get update && apt-get install -y --no-install-recommends \
      python3.10 python3.10-venv python3.10-dev \
 && rm -rf /var/lib/apt/lists/* \
 && python3.10 -m venv /opt/musetalk-py310
ENV MT_PY=/opt/musetalk-py310/bin/python
ENV MT_PIP=/opt/musetalk-py310/bin/pip

# Pin torch to MuseTalk's recipe (torch 2.0.1 + cu118)
RUN $MT_PIP install --no-cache-dir --upgrade pip setuptools wheel \
 && $MT_PIP install --no-cache-dir \
      torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
      --index-url https://download.pytorch.org/whl/cu118

# MuseTalk's official requirements.txt — exact pins
RUN $MT_PIP install --no-cache-dir \
      diffusers==0.30.2 accelerate==0.28.0 numpy==1.23.5 \
      opencv-python==4.9.0.80 soundfile==0.12.1 transformers==4.39.2 \
      huggingface_hub==0.30.2 librosa==0.11.0 einops==0.8.1 \
      ffmpeg-python moviepy omegaconf gdown requests "imageio[ffmpeg]" \
      pydub

# Pre-install chumpy with --no-build-isolation (its setup.py uses legacy
# imp.* APIs and trips pip's isolated build env). mmpose pulls chumpy as a
# transitive dep; if mim hits chumpy after build-isolation kicks in, the
# whole mim install fails.
RUN $MT_PIP install --no-cache-dir --no-build-isolation chumpy

# MMLab via mim (works on Python 3.10 — fails on 3.12 because openmim drags
# in legacy setuptools that calls the removed pkgutil.ImpImporter)
RUN $MT_PIP install --no-cache-dir -U openmim \
 && /opt/musetalk-py310/bin/mim install mmengine \
 && /opt/musetalk-py310/bin/mim install "mmcv==2.0.1" \
 && /opt/musetalk-py310/bin/mim install "mmdet==3.1.0" \
 && /opt/musetalk-py310/bin/mim install "mmpose==1.1.0"

# Clone AIFSH MuseTalk wrapper + apply two patches:
#   1. cuda_malloc import is broken (no such PyPI package; was a comfy
#      internal that got moved). Replace with a torch stub.
#   2. inference.py:37 has a typo — face_model_pth path has stray
#      commas+quotes baked in. Fix to proper os.path.join.
RUN git clone --depth 1 https://github.com/AIFSH/ComfyUI-MuseTalk_FSH /opt/musetalk-py310/aifsh \
 && for f in /opt/musetalk-py310/aifsh/inference.py \
            /opt/musetalk-py310/aifsh/inference_realtime.py; do \
      sed -i 's|^from cuda_malloc import cuda_malloc_supported$|import torch as _t\ndef cuda_malloc_supported(): return _t.cuda.is_available()|' "$f"; \
    done \
 && sed -i "s|face_model_pth = os.path.join(parent_directory,\"models','face-parse-bisent','79999_iter.pth\")|face_model_pth = os.path.join(parent_directory, 'models', 'face-parse-bisent', '79999_iter.pth')|" \
      /opt/musetalk-py310/aifsh/inference.py

# Standalone runner script (called by the ComfyUI bridge node via subprocess)
COPY musetalk_runner.py /opt/musetalk-py310/runner.py

# Smoke check — fails the build early if the side venv didn't compose right
RUN $MT_PY -c "import sys; sys.path.insert(0,'/opt/musetalk-py310/aifsh'); from mmpose.apis import init_model; print('mmpose.apis OK in py310 side venv')"

# Storyah custom nodes (audio→images shim + video shim + musetalk bridge)
COPY custom_nodes/ /comfyui/custom_nodes/storyah_custom/

# entrypoint.sh symlinks model dirs (IndexTTS-2 + MuseTalk) from the network
# volume into the paths their custom nodes expect at run time.
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh
ENTRYPOINT ["/opt/entrypoint.sh"]
