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


def test_codex_cli_image_generator_prefers_saved_path_from_stdout(
    tmp_path, monkeypatch
) -> None:
    codex_home = tmp_path / "codex_home"
    generated_dir = codex_home / "generated_images"
    session_dir = generated_dir / "019f09f7-test"
    output_dir = tmp_path / "out"
    saved = session_dir / "exact.png"

    def fake_which(command: str) -> str | None:
        return "C:/bin/codex.cmd" if command == "codex.cmd" else None

    def fake_run(*args, **kwargs):
        _ = args, kwargs
        session_dir.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(b"\x89PNG\r\n\x1a\nexact")
        (session_dir / "other.png").write_bytes(b"\x89PNG\r\n\x1a\nother")
        return SimpleNamespace(
            returncode=0,
            stdout=f"Saved at:\n\n`{saved}`",
            stderr="",
        )

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(codex_image_tool.shutil, "which", fake_which)
    monkeypatch.setattr(codex_image_tool.subprocess, "run", fake_run)

    result = codex_image_tool.CodexCLIImageGenerator()._run(
        "paint a readable action game style board",
        output_dir=str(output_dir),
    )

    copied = output_dir / "exact.png"
    assert result == f"saved: {copied}"
    assert copied.read_bytes().endswith(b"exact")


def test_codex_cli_image_generator_uses_session_png_from_stdout(
    tmp_path, monkeypatch
) -> None:
    codex_home = tmp_path / "codex_home"
    generated_dir = codex_home / "generated_images"
    session_id = "019f09f7-75ea-7f01-85e3-e9b1b4c46644"
    session_dir = generated_dir / session_id
    output_dir = tmp_path / "out"

    def fake_which(command: str) -> str | None:
        return "C:/bin/codex.cmd" if command == "codex.cmd" else None

    def fake_run(*args, **kwargs):
        _ = args, kwargs
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "own.png").write_bytes(b"\x89PNG\r\n\x1a\nown")
        other_dir = generated_dir / "019f09f7-0000-7000-8000-other000000"
        other_dir.mkdir(parents=True, exist_ok=True)
        (other_dir / "other.png").write_bytes(b"\x89PNG\r\n\x1a\nother")
        return SimpleNamespace(
            returncode=0,
            stdout=f"OpenAI Codex\nsession id: {session_id}\nGenerated one image.",
            stderr="",
        )

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(codex_image_tool.shutil, "which", fake_which)
    monkeypatch.setattr(codex_image_tool.subprocess, "run", fake_run)

    result = codex_image_tool.CodexCLIImageGenerator()._run(
        "paint a readable action game style board",
        output_dir=str(output_dir),
    )

    copied = output_dir / "own.png"
    assert result == f"saved: {copied}"
    assert copied.read_bytes().endswith(b"own")


def test_saved_pngs_from_output_prefers_saved_lines(tmp_path) -> None:
    error_path = tmp_path / "error.png"
    saved_path = tmp_path / "saved.png"
    error_path.write_bytes(b"old")
    saved_path.write_bytes(b"new")
    output = f"error: failed at {error_path} because stale\nsaved: {saved_path}"

    paths = codex_image_tool._saved_pngs_from_output(output)

    assert paths == [saved_path]


def test_session_pngs_from_output_requires_uuid(tmp_path) -> None:
    generated_dir = tmp_path / "generated_images"
    loose_session = generated_dir / "12345678901234567890aaaaaaaaaa"
    valid_session = generated_dir / "019f09f7-75ea-7f01-85e3-e9b1b4c46644"
    loose_session.mkdir(parents=True)
    valid_session.mkdir(parents=True)
    (loose_session / "loose.png").write_bytes(b"loose")
    valid_image = valid_session / "valid.png"
    valid_image.write_bytes(b"valid")

    loose = codex_image_tool._session_pngs_from_output(
        "session id: 12345678901234567890aaaaaaaaaa",
        generated_dir,
    )
    valid = codex_image_tool._session_pngs_from_output(
        "session id: 019f09f7-75ea-7f01-85e3-e9b1b4c46644",
        generated_dir,
    )

    assert loose == []
    assert valid == [valid_image]
