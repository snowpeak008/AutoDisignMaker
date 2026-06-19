#!/usr/bin/env python3
"""
本地化代码注入工具
替换硬编码中文字符串为 Loc.Get() 调用，并生成 LocalizationManager。
"""

import os
import re
from datetime import datetime
from pathlib import Path


def generate_localization_manager(output_dir):
    """
    生成 LocalizationManager.cs。
    """
    code = f"""// 自动生成 - 本地化管理器
// 生成时间：{datetime.now()}
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public static class Loc
{{
    private static Dictionary<string, string> _strings = new Dictionary<string, string>();
    private static string _currentLang = "zh-CN";

    public static void LoadLanguage(string lang)
    {{
        _currentLang = lang;
        _strings.Clear();
        string path = Path.Combine(Application.streamingAssetsPath, "Localization", lang + ".md");
        if (File.Exists(path))
        {{
            // 简单解析 JSON 文件（实际应使用 System.Text.Json/Newtonsoft.Json）
            string[] lines = File.ReadAllLines(path);
            foreach (string line in lines)
            {{
                if (line.Contains(": "))
                {{
                    int sep = line.IndexOf(": ");
                    string key = line.Substring(0, sep).Trim();
                    string value = line.Substring(sep + 2).Trim().Trim('"');
                    _strings[key] = value;
                }}
            }}
        }}
        Debug.Log($"Loc: 已加载语言 {{lang}}，共 {{_strings.Count}} 条");
    }}

    public static string Get(string key)
    {{
        if (_strings.TryGetValue(key, out string value))
            return value;
        return $"【{{key}}】"; // 未翻译时显示 key 本身，方便发现遗漏
    }}
}}
"""
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, "LocalizationManager.cs")
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return code_path


def inject_loc_calls(source_dir):
    """
    扫描源代码，将硬编码中文字符串替换为 Loc.Get("key")。
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        return []

    pattern = re.compile(r'"([^"]*[\u4e00-\u9fff][^"]*)"')
    injected_files = []

    for code_file in source_path.rglob("*.cs"):
        if 'LocalizationManager.cs' in str(code_file):
            continue

        content = code_file.read_text(encoding='utf-8')
        if 'Loc.Get(' in content:
            continue

        modified = False
        new_content = content
        for match in pattern.finditer(content):
            chinese_text = match.group(1)
            key = "text_" + chinese_text[:10].replace(' ', '_')
            new_content = new_content.replace(
                f'"{chinese_text}"',
                f'Loc.Get("{key}")'
            )
            modified = True

        if modified:
            code_file.write_text(new_content, encoding='utf-8')
            injected_files.append(str(code_file))
            print(f"  🌐 已注入本地化调用：{code_file.name}")

    return injected_files


def run_localization_injector(source_dir, output_dir):
    """
    执行本地化注入流水线。
    """
    manager_path = generate_localization_manager(output_dir)
    injected = inject_loc_calls(source_dir)
    return manager_path, injected
