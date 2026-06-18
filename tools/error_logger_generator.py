#!/usr/bin/env python3
"""
错误日志包裹工具
扫描生成的代码，自动在关键位置插入 try-catch 并生成 ErrorLogger 工具类。
"""

import os
import re
from datetime import datetime
from pathlib import Path


def generate_error_logger(output_dir):
    """
    生成通用的 ErrorLogger.cs 工具类。
    """
    code = f"""// 自动生成 - 错误日志记录器
// 生成时间：{datetime.now()}
using System;
using System.IO;
using System.Text;

public enum ErrorLevel
{{
    Info,
    Warning,
    Error,
    Fatal
}}

public static class ErrorLogger
{{
    private static string _logDir = "logs";
    private static string _currentLogFile;

    static ErrorLogger()
    {{
        Directory.CreateDirectory(_logDir);
        _currentLogFile = Path.Combine(_logDir, $"error_{{DateTime.Now:yyyyMMdd_HHmm}}.log");
    }}

    public static void LogFatal(string source, string message)
    {{
        WriteLog(ErrorLevel.Fatal, source, message);
    }}

    public static void LogError(string source, string message)
    {{
        WriteLog(ErrorLevel.Error, source, message);
    }}

    public static void LogWarning(string source, string message)
    {{
        WriteLog(ErrorLevel.Warning, source, message);
    }}

    public static void LogInfo(string source, string message)
    {{
        WriteLog(ErrorLevel.Info, source, message);
    }}

    private static void WriteLog(ErrorLevel level, string source, string message)
    {{
        string logLine = $"[{{DateTime.Now:yyyy-MM-dd HH:mm:ss}}] {{level.ToString().ToUpper()}} | {{source}}: {{message}}";
        try
        {{
            File.AppendAllText(_currentLogFile, logLine + Environment.NewLine);
        }}
        catch
        {{
            // 日志写入失败时静默处理，避免无限递归
        }}
    }}
}}
"""
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, "ErrorLogger.cs")
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return code_path


def wrap_method_with_trycatch(code_text, method_signature, source_name):
    """
    为指定的方法体包裹 try-catch。
    """
    # 简化处理：在方法体开头插入 try，结尾插入 catch
    # 实际项目可用 Roslyn 等更精确的方式
    pattern = re.compile(rf'({re.escape(method_signature)}\s*\{{\s*)', re.DOTALL)
    wrapped = pattern.sub(
        r'\1try { ',
        code_text
    )
    # 在方法结尾的 } 前插入 catch
    # 这里只做示例，真实实现应更严谨
    return wrapped


def wrap_code_with_logging(source_dir, output_dir):
    """
    扫描源代码目录，为关键方法包裹 try-catch 并添加日志调用。
    返回包裹后的文件列表。
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"源代码目录不存在：{source_dir}")
        return []

    wrapped_files = []
    for code_file in source_path.rglob("*.cs"):
        # 跳过自动生成的代码和工具类
        if 'ErrorLogger.cs' in str(code_file) or 'PerfMonitor.cs' in str(code_file) or 'UIManager.cs' in str(code_file):
            continue

        content = code_file.read_text(encoding='utf-8')

        # 简单检查是否已包含 ErrorLogger，避免重复包裹
        if 'ErrorLogger.Log' in content:
            continue

        # 包裹 Update/FixedUpdate/LateUpdate/Awake/Start 等生命周期方法
        modified = False
        for method in ['void Update()', 'void FixedUpdate()', 'void LateUpdate()',
                       'void Awake()', 'void Start()', 'void OnEnable()', 'void OnDisable()']:
            if method in content:
                # 简单替换：在方法体开头插入 try，在结尾的 } 前插入 catch
                # 这里做极简处理：在第一个 { 之后插入 try
                lines = content.split('\n')
                new_lines = []
                in_target_method = False
                for line in lines:
                    if method in line and '{' in line:
                        in_target_method = True
                        new_lines.append(line)
                        new_lines.append('        try {')
                        continue
                    if in_target_method and line.strip() == '}':
                        # 方法结束前插入 catch
                        new_lines.append('        }')
                        new_lines.append('        catch (Exception ex) {')
                        new_lines.append(f'            ErrorLogger.LogFatal("{code_file.stem}.{method.replace("void ", "").replace("()", "")}", ex.ToString());')
                        new_lines.append('            throw;')
                        new_lines.append('        }')
                        new_lines.append('    }')
                        in_target_method = False
                        modified = True
                        continue
                    new_lines.append(line)
                if modified:
                    content = '\n'.join(new_lines)
                    # 需要在文件顶部添加 using System;
                    if 'using System;' not in content:
                        content = 'using System;\n' + content
        if modified:
            wrapped_files.append(str(code_file))
            code_file.write_text(content, encoding='utf-8')
            print(f"  📦 已包裹：{code_file.name}")

    return wrapped_files


def run_error_logger_pipeline(source_dir, output_dir):
    """
    执行错误日志包裹流水线：
    1. 生成 ErrorLogger.cs
    2. 扫描并包裹源代码
    返回 (logger_path, wrapped_files)
    """
    logger_path = generate_error_logger(output_dir)
    wrapped_files = wrap_code_with_logging(source_dir, output_dir)
    return logger_path, wrapped_files