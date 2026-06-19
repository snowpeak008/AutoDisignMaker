import subprocess
import os
from core.utils.base_tool import BaseTool
from core.utils.process_utils import child_process_env, hidden_subprocess_kwargs

class CompileChecker(BaseTool):
    name: str = "Compile Checker"
    description: str = "在指定目录下执行编译命令，返回编译结果。默认使用 Unity 编译命令。"

    def _run(self, command: str = None) -> str:
        work_dir = os.getenv("DEV_WORK_DIR", os.getcwd())
        cmd = command or f'Unity -batchmode -quit -projectPath "{work_dir}" -executeMethod BuildPipeline.BuildPlayer'
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=300,
                **hidden_subprocess_kwargs(env=child_process_env()),
            )
            if result.returncode == 0 and "error" not in result.stdout.lower():
                return "PASS: 编译成功，0 Error。"
            else:
                return f"FAIL: 编译失败。\n{result.stdout}\n{result.stderr}"
        except Exception as e:
            return f"编译检查异常: {str(e)}"
