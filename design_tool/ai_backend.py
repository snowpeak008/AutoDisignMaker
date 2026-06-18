import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from design_tool.ai_schema import AI_RESPONSE_SCHEMA, AI_RESPONSE_SCHEMAS
from design_tool.ai_llm_backend import BackendCapabilities, LLMBackend


class CodexUnavailableError(RuntimeError):
    pass


API_CONFIG_FILE = "ai_api_config.json"


def toml_cli_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(str(value), ensure_ascii=False)


def load_project_api_config(runtime_root):
    path = Path(runtime_root) / API_CONFIG_FILE
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "activeProfile": "global_codex",
            "description": "使用全局 Codex 配置",
            "env": {},
            "config": {},
            "codexHome": "",
            "ignoreUserConfig": False,
            "profile": "",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CodexUnavailableError(f"AI API 配置文件读取失败：{path}；{error}") from error
    if not isinstance(payload, dict):
        raise CodexUnavailableError(f"AI API 配置文件必须是 JSON object：{path}")

    profiles = payload.get("profiles")
    active = str(payload.get("activeProfile") or payload.get("active_profile") or "").strip()
    if isinstance(profiles, dict):
        if not active:
            active = next(iter(profiles), "")
        profile_payload = profiles.get(active)
        if not isinstance(profile_payload, dict):
            raise CodexUnavailableError(f"AI API 配置 profile 不存在或格式错误：{active}")
    else:
        active = active or "default"
        profile_payload = payload

    env = profile_payload.get("env", {})
    config = profile_payload.get("config", {})
    if not isinstance(env, dict):
        raise CodexUnavailableError(f"AI API 配置 env 必须是 object：{active}")
    if not isinstance(config, dict):
        raise CodexUnavailableError(f"AI API 配置 config 必须是 object：{active}")

    codex_home = str(profile_payload.get("codexHome") or profile_payload.get("codex_home") or "").strip()
    if not codex_home and path.exists():
        safe_profile = re.sub(r"[^0-9A-Za-z_.-]+", "_", active or "default").strip("._") or "default"
        codex_home = str(Path(".codex_profiles") / safe_profile)
    if codex_home:
        codex_home_path = Path(codex_home)
        if not codex_home_path.is_absolute():
            codex_home_path = Path(runtime_root) / codex_home_path
        codex_home = str(codex_home_path)

    return {
        "path": str(path),
        "exists": True,
        "activeProfile": active,
        "description": str(profile_payload.get("description", "")),
        "env": {str(key): str(value) for key, value in env.items() if str(key).strip()},
        "config": {str(key): value for key, value in config.items() if str(key).strip()},
        "codexHome": codex_home,
        "ignoreUserConfig": bool(profile_payload.get("ignoreUserConfig", profile_payload.get("ignore_user_config", False))),
        "writeCodexAuthFile": bool(profile_payload.get("writeCodexAuthFile", profile_payload.get("write_codex_auth_file", True))),
        "profile": str(profile_payload.get("codexProfile") or profile_payload.get("profile") or "").strip(),
    }


def project_api_config_summary(runtime_root):
    try:
        config = load_project_api_config(runtime_root)
    except CodexUnavailableError as error:
        return {"activeProfile": "配置错误", "description": str(error), "exists": True}
    return {
        "activeProfile": config.get("activeProfile", ""),
        "description": config.get("description", ""),
        "exists": config.get("exists", False),
        "model": config.get("config", {}).get("model", ""),
        "baseUrl": config.get("config", {}).get("model_providers.OpenAI.base_url", ""),
    }


class CodexProcessRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._processes = set()
        self._closed = False

    @property
    def closed(self):
        with self._lock:
            return self._closed

    def register(self, process):
        with self._lock:
            if self._closed:
                return False
            self._processes.add(process)
            return True

    def unregister(self, process):
        with self._lock:
            self._processes.discard(process)

    def active_count(self):
        with self._lock:
            return len(self._processes)

    def cancel_all(self):
        with self._lock:
            self._closed = True
            processes = list(self._processes)
            self._processes.clear()
        for process in processes:
            terminate_process_tree(process)


@dataclass
class CodexRunResult:
    payload: dict
    session_id: str = ""
    raw_output: str = ""
    raw_events: list | None = None
    duration_seconds: float = 0.0
    first_event_seconds: float | None = None
    response_chars: int = 0
    api_profile: str = ""
    api_model: str = ""
    api_base_url: str = ""


def codex_command_path():
    if sys.platform.startswith("win"):
        for name in ("codex.cmd", "codex.exe", "codex.ps1", "codex"):
            path = shutil.which(name)
            if path:
                return path
    return shutil.which("codex")


def codex_available():
    return bool(codex_command_path())


def command_for_codex(args):
    path = codex_command_path()
    if not path:
        raise CodexUnavailableError("Codex CLI not found")
    if sys.platform.startswith("win") and path.lower().endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            path,
            *args,
        ]
    return [path, *args]


def hidden_subprocess_kwargs():
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
    return kwargs


def terminate_process_tree(process):
    if process.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            text=True,
        )
    else:
        process.kill()


def write_schema_file(runtime_root, schema=None, name="codex_interview_response.schema.json"):
    schema_dir = Path(runtime_root) / "ai_runtime"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = schema_dir / name
    schema_path.write_text(json.dumps(schema or AI_RESPONSE_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
    return schema_path


def write_prompt_file(runtime_root, prompt):
    prompt_dir = Path(runtime_root) / "ai_runtime"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / "codex_interview_prompt.json"
    prompt_path.write_text(str(prompt or ""), encoding="utf-8")
    return prompt_path


def parse_json_lines(output):
    events = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def extract_session_id(events):
    uuid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    keys = ("session_id", "sessionId", "conversation_id", "conversationId", "thread_id", "threadId")
    for event in events or []:
        stack = [event]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                for key in keys:
                    item = value.get(key)
                    if isinstance(item, str) and item:
                        return item
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
            elif isinstance(value, str) and uuid_pattern.match(value):
                return value
    return ""


def extract_json_object(text):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty Codex response")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        payload = json.loads(fenced.group(1))
        if isinstance(payload, dict):
            return payload

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        payload = json.loads(text[start:end + 1])
        if isinstance(payload, dict):
            return payload
    raise ValueError("Codex response did not contain a JSON object")


class CodexCliBackend(LLMBackend):
    def __init__(self, runtime_root, workdir=None, timeout_seconds=90, process_registry=None):
        self.runtime_root = Path(runtime_root)
        self.workdir = Path(workdir or runtime_root)
        self.timeout_seconds = timeout_seconds
        self.process_registry = process_registry

    def active_api_config(self):
        return load_project_api_config(self.runtime_root)

    def codex_config_args(self):
        api_config = self.active_api_config()
        args = []
        if api_config.get("ignoreUserConfig"):
            args.append("--ignore-user-config")
        if api_config.get("profile"):
            args.extend(["--profile", api_config["profile"]])
        for key, value in api_config.get("config", {}).items():
            args.extend(["-c", f"{key}={toml_cli_value(value)}"])
        return args

    def subprocess_env(self):
        api_config = self.active_api_config()
        env = dict(os.environ)
        if api_config.get("codexHome"):
            env["CODEX_HOME"] = api_config["codexHome"]
        env.update(api_config.get("env", {}))
        return env

    def ensure_project_codex_auth(self):
        api_config = self.active_api_config()
        codex_home = api_config.get("codexHome")
        api_key = api_config.get("env", {}).get("OPENAI_API_KEY", "")
        if not codex_home or not api_key or not api_config.get("writeCodexAuthFile", True):
            return
        auth_dir = Path(codex_home)
        auth_dir.mkdir(parents=True, exist_ok=True)
        auth_path = auth_dir / "auth.json"
        payload = {
            "auth_mode": "apikey",
            "OPENAI_API_KEY": api_key,
        }
        auth_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def capabilities(self):
        return BackendCapabilities(
            name="codex_cli",
            supports_prompt_cache=False,
            supports_streaming=False,
            max_prompt_tokens=None,
            cost_estimate="external_codex_cli",
        )

    def build_args(self, prompt_path, output_path, schema_path, session_id="", use_schema=True):
        prompt_arg = (
            f"Read the UTF-8 file at {prompt_path}. Follow the instructions in that file. "
            "Return only the final JSON object requested by the instructions. Do not edit files."
        )
        schema_args = ["--output-schema", str(schema_path)] if use_schema else []
        config_args = self.codex_config_args()
        if session_id:
            return [
                "exec",
                *config_args,
                "resume",
                "--skip-git-repo-check",
                "--json",
                *schema_args,
                "-o",
                str(output_path),
                session_id,
                prompt_arg,
            ]
        return [
            "exec",
            *config_args,
            "--skip-git-repo-check",
            "-C",
            str(self.workdir),
            "-s",
            "read-only",
            "--json",
            *schema_args,
            "-o",
            str(output_path),
            prompt_arg,
        ]

    def run_codex_command(self, args):
        if self.process_registry and self.process_registry.closed:
            raise CodexUnavailableError("Codex CLI run cancelled")
        self.ensure_project_codex_auth()
        command = command_for_codex(args)
        process = None
        try:
            started_at = time.perf_counter()
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.workdir),
                env=self.subprocess_env(),
                **hidden_subprocess_kwargs(),
            )
            if self.process_registry and not self.process_registry.register(process):
                terminate_process_tree(process)
                raise CodexUnavailableError("Codex CLI run cancelled")
            stdout_chunks = []
            stderr_chunks = []
            first_event_seconds = {"value": None}

            def read_stream(stream, chunks, mark_first=False):
                try:
                    for line in iter(stream.readline, ""):
                        if mark_first and first_event_seconds["value"] is None and line.strip():
                            first_event_seconds["value"] = time.perf_counter() - started_at
                        chunks.append(line)
                finally:
                    try:
                        stream.close()
                    except OSError:
                        pass

            stdout_thread = threading.Thread(
                target=read_stream,
                args=(process.stdout, stdout_chunks, True),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=read_stream,
                args=(process.stderr, stderr_chunks, False),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()
            try:
                process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired as error:
                terminate_process_tree(process)
                raise CodexUnavailableError(f"Codex CLI timed out after {self.timeout_seconds} seconds") from error
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
        except OSError as error:
            raise CodexUnavailableError(str(error)) from error
        finally:
            if process is not None and self.process_registry:
                self.process_registry.unregister(process)
        duration_seconds = time.perf_counter() - started_at
        return (
            process.returncode,
            "".join(stdout_chunks),
            "".join(stderr_chunks),
            {
                "durationSeconds": duration_seconds,
                "firstEventSeconds": first_event_seconds["value"],
            },
        )

    def run_json_task(self, prompt, schema=None, schema_name="codex_task_response.schema.json", session_id=""):
        if not codex_available():
            raise CodexUnavailableError("Codex CLI not available")

        schema_path = write_schema_file(self.runtime_root, schema=schema or AI_RESPONSE_SCHEMA, name=schema_name)
        with tempfile.TemporaryDirectory(prefix="ai_codex_", dir=str(self.runtime_root / "ai_runtime")) as temp_dir:
            prompt_path = Path(temp_dir) / "prompt.txt"
            prompt_path.write_text(str(prompt or ""), encoding="utf-8")
            output_path = Path(temp_dir) / "last_message.json"
            args = self.build_args(prompt_path, output_path, schema_path, session_id=session_id, use_schema=True)
            returncode, stdout, stderr, timings = self.run_codex_command(args)

            raw = "\n".join(part for part in (stdout, stderr) if part)
            if returncode != 0:
                raise CodexUnavailableError(raw.strip() or f"Codex exited with code {returncode}")

            events = parse_json_lines(stdout)
            final_text = output_path.read_text(encoding="utf-8") if output_path.exists() else stdout
            payload = extract_json_object(final_text)
            api_config = self.active_api_config()
            codex_config = api_config.get("config", {})
            return CodexRunResult(
                payload=payload,
                session_id=extract_session_id(events) or session_id,
                raw_output=raw,
                raw_events=events,
                duration_seconds=float(timings.get("durationSeconds", 0.0) or 0.0),
                first_event_seconds=timings.get("firstEventSeconds"),
                response_chars=len(final_text),
                api_profile=api_config.get("activeProfile", ""),
                api_model=str(codex_config.get("model", "")),
                api_base_url=str(codex_config.get("model_providers.OpenAI.base_url", "")),
            )

    def run_turn(self, prompt, session_id="", schema_mode="turn"):
        schema_mode = schema_mode if schema_mode in AI_RESPONSE_SCHEMAS else "turn"
        return self.run_json_task(
            prompt,
            schema=AI_RESPONSE_SCHEMAS.get(schema_mode, AI_RESPONSE_SCHEMA),
            schema_name=f"codex_interview_{schema_mode}_response.schema.json",
            session_id=session_id,
        )
