import os
import subprocess
import sys
from pathlib import Path
from tools.process_utils import child_process_env, hidden_subprocess_kwargs

class EnvironmentChecker:
    def __init__(self, env_config_path):
        with open(env_config_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        from tools.structured_md import loads_data
        try:
            self.config = loads_data(raw) or {}
        except Exception:
            from tools.md_parser import parse_md_output
            self.config = parse_md_output(raw, output_name="dev_environment") or {}
        self.results = []

    def check_all(self):
        self._check_engine()
        self._check_sdks()
        self._check_python_packages()
        self._check_system_tools()
        return self.results

    def fix_python_packages(self):
        """自动安装缺失的 Python 包"""
        packages = self.config.get('python', [])
        if not packages:
            print("没有需要安装的 Python 包。")
            return

        missing = []
        for pkg_spec in packages:
            pkg_name = pkg_spec.split('>=')[0].split('==')[0].strip()
            try:
                __import__(pkg_name)
            except ImportError:
                missing.append(pkg_spec)

        if missing:
            print(f"正在安装缺失的 Python 包：{', '.join(missing)}")
            try:
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install'] + missing,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    **hidden_subprocess_kwargs(env=child_process_env()),
                )
                print("✅ Python 包安装完成。")
            except Exception as e:
                print(f"❌ Python 包自动安装失败：{e}")
                print("请手动执行：pip install " + " ".join(missing))
        else:
            print("✅ 所有 Python 包已就绪。")

    def _check_engine(self):
        engine = self.config.get('engine', {})
        name = engine.get('name', 'Unity')
        version = engine.get('version', '')
        if name == 'Unity':
            try:
                result = subprocess.run(
                    ['Unity', '-version'],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    **hidden_subprocess_kwargs(env=child_process_env()),
                )
                if result.returncode == 0 and version in result.stdout:
                    self.results.append(f"✅ Unity 版本匹配：{version}")
                else:
                    self.results.append(f"❌ Unity 未安装或版本不符，需要 {version}")
            except:
                self.results.append(f"❌ 未找到 Unity 命令")

    def _check_sdks(self):
        sdks = self.config.get('sdks', [])
        for sdk in sdks:
            if 'NET' in sdk:
                try:
                    result = subprocess.run(
                        ['dotnet', '--version'],
                        capture_output=True,
                        text=True,
                        **hidden_subprocess_kwargs(env=child_process_env()),
                    )
                    if result.returncode == 0:
                        self.results.append(f"✅ .NET SDK 已安装：{result.stdout.strip()}")
                    else:
                        self.results.append(f"❌ .NET SDK 未安装")
                except:
                    self.results.append(f"❌ dotnet 命令不可用")

    def _check_python_packages(self):
        packages = self.config.get('python', [])
        for pkg_spec in packages:
            pkg_name = pkg_spec.split('>=')[0].split('==')[0].strip()
            try:
                __import__(pkg_name)
                self.results.append(f"✅ Python 包 {pkg_name} 已安装")
            except ImportError:
                self.results.append(f"❌ Python 包 {pkg_name} 未安装")

    def _check_system_tools(self):
        tools = self.config.get('tools', [])
        for tool in tools:
            cmd = 'where' if os.name == 'nt' else 'which'
            try:
                result = subprocess.run(
                    [cmd, tool],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    **hidden_subprocess_kwargs(env=child_process_env()),
                )
                if result.returncode == 0:
                    self.results.append(f"✅ 工具 {tool} 可用")
                else:
                    self.results.append(f"❌ 工具 {tool} 未找到")
            except:
                self.results.append(f"❌ 无法检查工具 {tool}")
