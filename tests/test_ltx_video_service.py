import hashlib
import subprocess
from types import SimpleNamespace

import pytest

import imageio_ffmpeg
from backend import ltx_video_service
from backend.app import extract_ltx_background_frames


def test_visual_prompt_uses_requested_topic_scene_and_concepts():
    prompt = ltx_video_service.visual_prompt(
        "What is an apple?",
        {
            "heading": "An apple grows on a tree",
            "narration": "An apple is an edible fruit that grows on apple trees.",
            "visual": {"nodes": [{"label": "orchard"}], "keywords": ["red fruit"]},
        },
    )

    assert "What is an apple?" in prompt
    assert "An apple grows on a tree" in prompt
    assert "orchard" in prompt
    assert "red fruit" in prompt
    assert "No written words" in prompt


def test_checkpoint_is_verified_and_cached_by_file_fingerprint(tmp_path, monkeypatch):
    checkpoint = tmp_path / "checkpoint.safetensors"
    checkpoint.write_bytes(b"valid checkpoint fixture")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    monkeypatch.setattr(ltx_video_service, "CHECKPOINT_SHA256", digest)

    ltx_video_service._verified_checkpoint(checkpoint)
    marker = checkpoint.with_suffix(checkpoint.suffix + ".sha256")
    assert marker.is_file()
    ltx_video_service._verified_checkpoint(checkpoint)

    checkpoint.write_bytes(b"corrupted checkpoint")
    with pytest.raises(RuntimeError, match="SHA-256 verification"):
        ltx_video_service._verified_checkpoint(checkpoint)


def test_vram_preflight_fails_clearly_when_less_than_five_gib_is_free():
    cuda = SimpleNamespace(
        get_device_properties=lambda _device: SimpleNamespace(
            total_memory=6 * 1024**3, name="Test GPU"
        ),
        mem_get_info=lambda _device: (4 * 1024**3, 6 * 1024**3),
    )
    torch = SimpleNamespace(cuda=cuda)

    with pytest.raises(RuntimeError, match="4.0 GiB free"):
        ltx_video_service.check_vram(torch)


def test_vram_preflight_accepts_a_marketed_six_gib_gpu_with_rounding():
    total = 6141 * 1024**2
    free = 5 * 1024**3
    cuda = SimpleNamespace(
        get_device_properties=lambda _device: SimpleNamespace(
            total_memory=total, name="RTX 4050 Laptop GPU"
        ),
        mem_get_info=lambda _device: (free, total),
    )

    assert ltx_video_service.check_vram(SimpleNamespace(cuda=cuda)) == (free, total)


@pytest.mark.parametrize("frame_count", [16, 17, 18])
def test_generated_clip_extraction_produces_the_expected_background_frames(tmp_path, frame_count):
    clip = tmp_path / "source.mp4"
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=448x256:r=12",
            "-frames:v",
            str(frame_count),
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    # A previous attempt must never supply a missing final frame.
    (tmp_path / "background-0-16.png").write_bytes(b"stale")
    if frame_count != 17:
        with pytest.raises(ValueError, match=f"produced {frame_count} usable"):
            extract_ltx_background_frames(clip, tmp_path, 0)
        return
    frames = extract_ltx_background_frames(clip, tmp_path, 0)

    assert len(frames) == 17
    assert all(path.is_file() for path in frames)


def test_missing_assets_fail_without_network_or_creating_model_directory(tmp_path, monkeypatch):
    model_dir = tmp_path / "not-installed"
    monkeypatch.setattr(ltx_video_service, "MODEL_DIR", model_dir)
    with pytest.raises(RuntimeError, match="no weights were downloaded"):
        ltx_video_service.ensure_assets(lambda *args: None)
    assert not model_dir.exists()


def test_text_encoder_requires_local_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(ltx_video_service, "MODEL_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="downloads are disabled"):
        ltx_video_service.local_text_encoder()

@pytest.mark.parametrize("failure", [RuntimeError("extraction failed"), KeyboardInterrupt("cancelled")])
def test_failed_or_cancelled_extraction_cleans_frames_and_never_completes(tmp_path, monkeypatch, failure):
    import importlib
    appmod = importlib.import_module("backend.app")
    from backend.schemas import LessonRequest
    updates = []
    events = []
    monkeypatch.setattr(appmod, "OUTPUT", tmp_path)
    monkeypatch.setattr(appmod, "update", lambda ident, **fields: updates.append(fields))
    monkeypatch.setattr(appmod, "installed_voices", lambda: [{"language": "en", "localAvailable": True}])
    monkeypatch.setattr(appmod, "audit", lambda *args: {"passed": True})
    monkeypatch.setattr(appmod, "speech", lambda *args: 31)
    monkeypatch.setattr(appmod, "fit_narration", lambda paths, *args: ([(paths[0],31,60)],1.0))
    monkeypatch.setattr(appmod, "require_ltx_runtime", lambda: None)
    monkeypatch.setattr(appmod, "unload_ollama_model", lambda *args: events.append("unload"))
    def generate(*args):
        events.append("generate")
        assert events == ["unload", "generate"]
        return [tmp_path / "test-clip.mp4"]
    monkeypatch.setattr(appmod, "generate_scene_clips", generate)
    def extract(clip, folder, index):
        (folder / "partial.png").write_bytes(b"partial frame")
        raise failure
    monkeypatch.setattr(appmod, "extract_ltx_background_frames", extract)
    result = SimpleNamespace(intent="educational", lesson=None, model_dump=lambda: {
        "lesson": {"scenes": [{"id": "one", "heading": "One", "narration": "One scene."}]}
    })
    if isinstance(failure, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt, match="cancelled"):
            appmod.run("test-job", LessonRequest(topic="Test lesson",videoEngine="ltx"), prepared=result)
    else:
        appmod.run("test-job", LessonRequest(topic="Test lesson",videoEngine="ltx"), prepared=result)
    assert not list((tmp_path / "test-job").glob("ltx-frames-*"))
    assert not (tmp_path / "test-job" / "lesson.json").exists()
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["result"] is None
    assert not any(item.get("status") == "completed" for item in updates)


def test_insufficient_free_vram_never_loads_assets_or_pipeline(tmp_path, monkeypatch):
    cuda = SimpleNamespace(
        get_device_properties=lambda _: SimpleNamespace(total_memory=6 * 1024**3, name="GPU"),
        mem_get_info=lambda _: (4 * 1024**3, 6 * 1024**3),
    )
    monkeypatch.setattr(ltx_video_service, "require_runtime", lambda: SimpleNamespace(cuda=cuda))
    monkeypatch.setattr(ltx_video_service, "ensure_assets", lambda *_: pytest.fail("Loaded assets before VRAM gate"))
    with pytest.raises(RuntimeError, match="4.0 GiB free"):
        ltx_video_service.generate_scene_clips("test", [], tmp_path, lambda *args: None)
