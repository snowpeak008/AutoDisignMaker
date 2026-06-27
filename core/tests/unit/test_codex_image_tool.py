from __future__ import annotations

from types import SimpleNamespace

from tools.asset_production import codex_image_tool


def test_codex_cli_image_generator_copies_new_png(tmp_path, monkeypatch) -> None:
    codex_home = tmp_path / "codex_home"
    generated_dir = codex_home / "generated_images"
    output_dir = tmp_path / "out"
    captured: dict[str, object] = {}

    def fake_which(command: str) -> str | None:
        return "C:/bin/codex.cmd" if command == "codex.cmd" else None

    def fake_run(args, input, capture_output, text, timeout, **kwargs):
        captured["args"] = args
        captured["input"] = input
        captured["kwargs"] = kwargs
        session_dir = generated_dir / "019f09f7-test"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "style.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return SimpleNamespace(returncode=0, stdout="done", stderr="")

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(codex_image_tool.shutil, "which", fake_which)
    monkeypatch.setattr(codex_image_tool.subprocess, "run", fake_run)

    result = codex_image_tool.CodexCLIImageGenerator()._run(
        "paint a readable action game style board",
        output_dir=str(output_dir),
    )

    copied = output_dir / "style.png"
    assert copied.read_bytes().startswith(b"\x89PNG")
    assert result == f"saved: {copied}"
    assert captured["args"][0] == "C:/bin/codex.cmd"
    assert captured["args"][1] == "exec"
    assert captured["args"][-1] != "-"
    assert captured["kwargs"]["stdin"] is None
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"
    assert "image_gen tool" in str(captured["input"])
