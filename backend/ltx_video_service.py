"""Local LTX-Video 2B FP8 scene generation using the official Lightricks pipeline."""
import gc
import hashlib
import importlib
import json
import threading
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models" / "ltx-video"
MODEL_REPO = "Lightricks/LTX-Video"
MODEL_REVISION = "8984fa25007f376c1a299016d0957a37a2f797bb"
CHECKPOINT = "ltxv-2b-0.9.8-distilled-fp8.safetensors"
CHECKPOINT_SHA256 = "d6d8fa8ed3a98346787c2503ac80fb5d7cebcf80e356b79a2ba361fbadf97e15"
UPSCALER = "ltxv-spatial-upscaler-0.9.8.safetensors"
WIDTH = 448
HEIGHT = 256
FRAME_COUNT = 17
FRAME_RATE = 12
MIN_FREE_VRAM = 5 * 1024**3
GPU_LOCK = threading.Lock()


def visual_prompt(topic: str, scene: dict) -> str:
    visual = scene.get("visual") or {}
    concepts = [
        node.get("label", "") if isinstance(node, dict) else str(node)
        for node in visual.get("nodes", [])
    ]
    concepts.extend(visual.get("keywords", []))
    concepts = list(dict.fromkeys(value.strip() for value in concepts if value.strip()))
    details = f" Key concepts: {', '.join(concepts[:5])}." if concepts else ""
    return (
        f"Create a concise, visually clear educational documentary shot about {topic}. "
        f"Show the specific idea in this scene: {scene['heading']}. "
        f"Visual context: {scene['narration']}.{details} "
        "Use realistic, coherent motion and a stable camera. No written words, labels, "
        "subtitles, logos, diagrams, split screens, or interface elements."
    )


def require_runtime():
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "LTX video dependencies are missing. Run SETUP-LTX-VIDEO.cmd first."
        ) from error
    if not torch.cuda.is_available():
        raise RuntimeError(
            "LTX video requires CUDA-enabled PyTorch and an NVIDIA GPU. "
            "Run SETUP-LTX-VIDEO.cmd; CPU-only LTX inference is disabled."
        )
    try:
        importlib.import_module("q8_kernels.integration.patch_transformer")
    except ImportError as error:
        raise RuntimeError(
            "The official LTX FP8 kernels are not installed. Run SETUP-LTX-VIDEO.cmd "
            "with CUDA Toolkit 12.8+ and Visual Studio C++ Build Tools available."
        ) from error
    return torch


def check_vram(torch) -> tuple[int, int]:
    properties = torch.cuda.get_device_properties(0)
    total = properties.total_memory
    free, _ = torch.cuda.mem_get_info(0)
    if free < MIN_FREE_VRAM:
        raise RuntimeError(
            f"LTX-Video needs at least 5 GiB of free GPU memory for the 448x256 FP8 "
            f"scene settings. {properties.name} has {free / 1024**3:.1f} GiB free "
            f"of {total / 1024**3:.1f} GiB. Close GPU-heavy apps and retry; no "
            "alternate video renderer was used."
        )
    return free, total


def unload_ollama_model(endpoint: str, model: str) -> None:
    try:
        with httpx.Client(trust_env=False, timeout=30) as client:
            response = client.get(endpoint + "/api/ps")
            response.raise_for_status()
            loaded = response.json().get("models", [])
            if not any(item.get("name", "").split(":")[0] == model.split(":")[0] for item in loaded):
                return
            response = client.post(
                endpoint + "/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
            )
            response.raise_for_status()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError(
            "Could not release the local Ollama planner from GPU memory before "
            f"LTX generation: {error}"
        ) from error


def _verified_checkpoint(path: Path) -> None:
    marker = path.with_suffix(path.suffix + ".sha256")
    stat = path.stat()
    fingerprint = f"{CHECKPOINT_SHA256}:{stat.st_size}:{stat.st_mtime_ns}"
    if marker.is_file() and marker.read_text(encoding="ascii").strip() == fingerprint:
        return
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != CHECKPOINT_SHA256:
        raise RuntimeError("The downloaded LTX FP8 checkpoint failed SHA-256 verification.")
    marker.write_text(fingerprint + "\n", encoding="ascii")


def ensure_assets(progress) -> tuple[Path, Path]:
    # Generation is strictly local: requesting a lesson never authorizes weights.
    checkpoint = MODEL_DIR / CHECKPOINT
    upscaler = MODEL_DIR / UPSCALER
    missing = [path.name for path in (checkpoint, upscaler) if not path.is_file()]
    if missing:
        raise RuntimeError(
            "LTX model weights are not installed: " + ", ".join(missing)
            + ". Explicit authorization and separate installation are required; no weights were downloaded."
        )
    progress(47, "checking_video", "Verifying local LTX weights (downloads disabled)")
    _verified_checkpoint(checkpoint)
    if upscaler.stat().st_size == 0:
        raise RuntimeError("The local LTX spatial upscaler is empty.")
    return checkpoint, upscaler


def local_text_encoder() -> Path:
    # The official factory loads text_encoder/ and tokenizer/ from this directory.
    path = MODEL_DIR / "text-encoder"
    if not (path / "text_encoder" / "config.json").is_file() or not (path / "tokenizer" / "tokenizer_config.json").is_file():
        raise RuntimeError(
            "The local LTX text encoder/tokenizer is missing at " + str(path)
            + ". Explicit authorization is required to install weights; downloads are disabled."
        )
    return path


def _make_pipeline(torch, checkpoint: Path, upscaler: Path):
    import yaml
    from ltx_video.inference import create_latent_upsampler, create_ltx_video_pipeline
    from ltx_video.pipelines.pipeline_ltx_video import LTXMultiScalePipeline

    config_path = ROOT / "backend" / "ltxv-2b-0.9.8-distilled-fp8.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    pipeline = create_ltx_video_pipeline(
        ckpt_path=str(checkpoint),
        precision=config["precision"],
        text_encoder_model_name_or_path=str(local_text_encoder()),
        sampler=config["sampler"],
        device="cpu",
        enhance_prompt=False,
        prompt_enhancer_image_caption_model_name_or_path=None,
        prompt_enhancer_llm_model_name_or_path=None,
    )
    # Use Accelerate hooks only; the official manual .cpu() path must not
    # compete with those hooks between the two multi-scale passes.
    pipeline.enable_model_cpu_offload(gpu_id=0)
    latent_upsampler = create_latent_upsampler(str(upscaler), "cuda")
    config["checkpoint_path"] = str(checkpoint)
    config["spatial_upscaler_model_path"] = str(upscaler)
    return LTXMultiScalePipeline(pipeline, latent_upsampler=latent_upsampler), config


def generate_scene_clips(topic: str, scenes: list[dict], output: Path, progress) -> list[Path]:
    torch = require_runtime()
    with GPU_LOCK:
        free, total = check_vram(torch)
        checkpoint, upscaler = ensure_assets(progress)
        pipeline = None
        try:
            progress(
                51,
                "loading_video_model",
                f"Loading LTX on the GPU with CPU offload ({free / 1024**3:.1f} GiB free)",
            )
            pipeline, pipeline_config = _make_pipeline(torch, checkpoint, upscaler)
            from imageio.v2 import mimwrite
            from ltx_video.utils.skip_layer_strategy import SkipLayerStrategy
            import numpy as np

            clips = []
            count = len(scenes)
            for index, scene in enumerate(scenes):
                progress(
                    53 + round(14 * index / count),
                    "generating_video",
                    f"Generating LTX educational scene {index + 1} of {count}",
                )
                seed = int.from_bytes(
                    hashlib.sha256(f"{topic}:{scene['id']}".encode("utf-8")).digest()[:4],
                    "big",
                )
                generator = torch.Generator(device="cuda").manual_seed(seed)
                config = dict(pipeline_config)
                config.pop("pipeline_type", None)
                config.pop("checkpoint_path", None)
                config.pop("spatial_upscaler_model_path", None)
                config.pop("text_encoder_model_name_or_path", None)
                config.pop("precision", None)
                config.pop("sampler", None)
                config.pop("stg_mode", None)
                frames = pipeline(
                    **config,
                    skip_layer_strategy=SkipLayerStrategy.AttentionValues,
                    generator=generator,
                    output_type="pt",
                    callback_on_step_end=None,
                    height=HEIGHT,
                    width=WIDTH,
                    num_frames=FRAME_COUNT,
                    frame_rate=FRAME_RATE,
                    prompt=visual_prompt(topic, scene),
                    prompt_attention_mask=None,
                    negative_prompt="text, subtitles, captions, logos, flicker, artifacts",
                    negative_prompt_attention_mask=None,
                    media_items=None,
                    conditioning_items=None,
                    is_video=True,
                    vae_per_channel_normalize=True,
                    image_cond_noise_scale=0.15,
                    mixed_precision=False,
                    offload_to_cpu=False,
                    device="cuda",
                    enhance_prompt=False,
                ).images[0]
                if tuple(frames.shape) != (3, FRAME_COUNT, HEIGHT, WIDTH):
                    raise RuntimeError(f"LTX returned unexpected C,F,H,W shape: {tuple(frames.shape)}")
                if not torch.isfinite(frames).all() or frames.min() < 0 or frames.max() > 1:
                    raise RuntimeError("LTX returned invalid pixels; expected finite values in [0, 1].")
                video = (frames.permute(1, 2, 3, 0).cpu().float().numpy() * 255).clip(0, 255).astype(np.uint8)
                clip = output / f"ltx-scene-{index}.mp4"
                mimwrite(clip, video, fps=FRAME_RATE, codec="libx264")
                if not clip.is_file() or clip.stat().st_size == 0:
                    raise RuntimeError(f"LTX did not produce scene clip {index + 1}.")
                clips.append(clip)
                del frames, video, generator
            progress(68, "video_ready", "LTX scene clips are ready for animation compositing")
            return clips
        except torch.cuda.OutOfMemoryError as error:
            raise RuntimeError(
                f"LTX ran out of GPU memory while generating at 448x256. "
                f"The GPU reports {free / 1024**3:.1f} GiB free of {total / 1024**3:.1f} GiB. "
                "Close GPU-heavy apps and retry; no substitute renderer was used."
            ) from error
        finally:
            if pipeline is not None:
                del pipeline
            gc.collect()
            torch.cuda.empty_cache()
