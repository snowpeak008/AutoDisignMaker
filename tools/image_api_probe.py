#!/usr/bin/env python3
"""Probe configured image generation providers with a real request.

Default usage tests only the active provider from providers.image_apis.active.
Reports are written with masked secrets and compact error details.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.image_api_config import ImageApiSettings, load_image_api_settings, mask_secret


DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "image_api_tests"


def _endpoint(settings: ImageApiSettings) -> str:
    return f"{settings.base_url.rstrip('/')}/{str(settings.endpoint or '').lstrip('/')}"


def _write_image(output_dir: Path, image_bytes: bytes, suffix: str = "png") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{int(time.time())}_image_probe.{suffix}"
    path.write_bytes(image_bytes)
    return path


def _extract_b64_from_responses_stream(response: requests.Response) -> tuple[str | None, list[str]]:
    final_b64 = None
    event_types: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if not line or not str(line).startswith("data:"):
            continue
        data_str = str(line)[len("data:"):].strip()
        if data_str == "[DONE]":
            break
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        event_type = str(event.get("type") or "")
        if event_type:
            event_types.append(event_type)
        if event_type == "response.output_item.done":
            item = event.get("item", {})
            if isinstance(item, dict) and item.get("type") == "image_generation_call" and item.get("result"):
                final_b64 = str(item["result"])
        elif event_type == "response.completed":
            output = event.get("response", {}).get("output", [])
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "image_generation_call" and item.get("result"):
                        final_b64 = str(item["result"])
    return final_b64, event_types


def _extract_b64_from_responses_json(data: dict[str, Any]) -> str | None:
    output = data.get("output", [])
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict) and item.get("type") == "image_generation_call" and item.get("result"):
                return str(item["result"])
    return None


def _post_responses_image_tool(
    settings: ImageApiSettings,
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    timeout: int,
) -> tuple[bytes | None, dict[str, Any]]:
    payload = {
        "model": settings.response_model or "gpt-5.5",
        "stream": True,
        "tool_choice": "auto",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "tools": [
            {
                "type": "image_generation",
                "model": settings.image_model,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "background": "opaque",
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(_endpoint(settings), json=payload, headers=headers, stream=True, timeout=timeout)
    details: dict[str, Any] = {
        "http_status": response.status_code,
        "endpoint": _endpoint(settings),
        "mode": settings.mode,
    }
    if response.status_code >= 400:
        details["error_body_excerpt"] = response.text[:1200]
        return None, details
    final_b64, event_types = _extract_b64_from_responses_stream(response)
    details["event_types"] = event_types[-20:]
    if not final_b64:
        details["error"] = "No image_generation_call result found in responses stream."
        return None, details
    return base64.b64decode(final_b64), details


def _post_images_generations(
    settings: ImageApiSettings,
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    timeout: int,
) -> tuple[bytes | None, dict[str, Any]]:
    payload = {
        "model": settings.image_model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "response_format": "b64_json",
    }
    if output_format:
        payload["output_format"] = output_format
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(_endpoint(settings), json=payload, headers=headers, timeout=timeout)
    details: dict[str, Any] = {
        "http_status": response.status_code,
        "endpoint": _endpoint(settings),
        "mode": settings.mode,
    }
    if response.status_code >= 400:
        details["error_body_excerpt"] = response.text[:1200]
        return None, details
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        details["error"] = f"Response was not JSON: {exc}"
        details["body_excerpt"] = response.text[:1200]
        return None, details
    b64_value = None
    images = data.get("data")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            b64_value = first.get("b64_json") or first.get("b64")
    if not b64_value:
        b64_value = _extract_b64_from_responses_json(data)
    if not b64_value:
        details["error"] = "No b64 image field found in JSON response."
        details["response_keys"] = sorted(data.keys())
        return None, details
    return base64.b64decode(str(b64_value)), details


def probe_provider(
    *,
    provider: str | None,
    prompt: str,
    output_dir: Path,
    size: str,
    quality: str,
    output_format: str,
    timeout: int,
) -> dict[str, Any]:
    started = time.time()
    settings = load_image_api_settings(provider)
    report: dict[str, Any] = {
        "provider_name": settings.name,
        "provider": settings.provider,
        "mode": settings.mode,
        "base_url": settings.base_url,
        "endpoint": _endpoint(settings),
        "image_model": settings.image_model,
        "response_model": settings.response_model,
        "api_key_masked": mask_secret(settings.api_key),
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "prompt": prompt,
        "status": "failed",
    }
    try:
        if settings.mode == "responses_image_tool":
            image_bytes, details = _post_responses_image_tool(settings, prompt, size, quality, output_format, timeout)
        elif settings.mode == "images_generations":
            image_bytes, details = _post_images_generations(settings, prompt, size, quality, output_format, timeout)
        else:
            raise RuntimeError(f"Unsupported image API mode: {settings.mode}")
        report["details"] = details
        if image_bytes:
            image_path = _write_image(output_dir, image_bytes, output_format)
            report["status"] = "success"
            report["image_path"] = str(image_path)
            report["image_bytes"] = len(image_bytes)
    except Exception as exc:
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    report["elapsed_seconds"] = round(time.time() - started, 3)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "image_api_probe_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe configured image generation provider.")
    parser.add_argument("--provider", default=None, help="Provider name under providers.image_apis. Defaults to active.")
    parser.add_argument("--prompt", default="A tiny underwater explorer icon, clean game asset, no text.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="high")
    parser.add_argument("--output-format", default="png")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    report = probe_provider(
        provider=args.provider,
        prompt=args.prompt,
        output_dir=Path(args.output_dir),
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
        timeout=args.timeout,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
