import subprocess
import os
from tools.base_tool import BaseTool
from tools.process_utils import child_process_env, hidden_subprocess_kwargs

class ClaudeCodeCLI(BaseTool):
    name: str = "ClaudeCodeCLI"
    description: str = "调用 Claude Code CLI 执行编码任务。输入为完整 prompt 字符串。"

    def _run(self, prompt: str) -> str:
        work_dir = os.getenv("DEV_WORK_DIR", os.getcwd())
        try:
            result = subprocess.run(
                ["claude", "code", "--prompt", prompt],
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=600,
                **hidden_subprocess_kwargs(env=child_process_env()),
            )
            out = result.stdout
            if result.returncode != 0:
                out += f"\n[EXIT:{result.returncode}] {result.stderr}"
            return out
        except Exception as e:
            return f"调用 Claude Code CLI 失败: {str(e)}"
