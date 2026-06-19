import subprocess
import os
from core.utils.base_tool import BaseTool
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs

class GitCLI(BaseTool):
    name: str = "GitCLI"
    description: str = "执行本地 Git 命令，仅限 init/add/commit/tag/status/log。禁止 push。"

    def _run(self, command: str) -> str:
        work_dir = os.getenv("DEV_WORK_DIR", os.getcwd())
        allowed = ["init", "add", "commit", "tag", "status", "log"]
        parts = command.strip().split()
        if not parts or parts[0] != "git" or (len(parts) > 1 and parts[1] not in allowed):
            return "禁止：只允许本地 init/add/commit/tag/status/log，禁止 push。"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=30,
                **hidden_subprocess_kwargs(env=child_process_env()),
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Git 命令失败: {str(e)}"
