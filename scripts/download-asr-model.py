"""Download the local Faster-Whisper tiny model used by Biryani.ai speech input."""
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "models" / "asr" / "faster-whisper-tiny"
TARGET.mkdir(parents=True, exist_ok=True)
snapshot_download(
    repo_id="Systran/faster-whisper-tiny",
    local_dir=TARGET,
    allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "preprocessor_config.json"],
)
print(f"Local speech-to-text model is ready: {TARGET}")