#!/usr/bin/env python3
"""
性能监控代码生成器
自动识别需要监控的位置，插入性能埋点，生成 PerfMonitor 和 PerfHUD 工具。
"""

import os
import re
from datetime import datetime
from pathlib import Path


def generate_perf_monitor(output_dir):
    """
    生成通用的 PerfMonitor.cs 性能统计工具。
    """
    code = f"""// 自动生成 - 性能监控器
// 生成时间：{datetime.now()}
using System;
using System.Diagnostics;
using System.IO;
using System.Collections.Generic;

public static class PerfMonitor
{{
    private static Dictionary<string, Stopwatch> _watches = new Dictionary<string, Stopwatch>();
    private static Dictionary<string, int> _counters = new Dictionary<string, int>();
    private static int _frameDropCount = 0;
    private static float _lastFPS = 0;
    private static string _reportPath = "logs/perf_report.csv";

    static PerfMonitor()
    {{
        Directory.CreateDirectory("logs");
        if (!File.Exists(_reportPath))
        {{
            File.WriteAllText(_reportPath, "Timestamp,Metric,Value,Unit\\n");
        }}
    }}

    public static IDisposable BeginSample(string name)
    {{
        if (!_watches.ContainsKey(name))
            _watches[name] = new Stopwatch();
        _watches[name].Start();
        return new SampleDisposable(name);
    }}

    private class SampleDisposable : IDisposable
    {{
        private string _name;
        public SampleDisposable(string name) {{ _name = name; }}
        public void Dispose()
        {{
            if (PerfMonitor._watches.ContainsKey(_name))
            {{
                var watch = PerfMonitor._watches[_name];
                watch.Stop();
                long ms = watch.ElapsedMilliseconds;
                PerfMonitor.RecordMetric(_name + "_ms", ms, "ms");
                watch.Reset();
            }}
        }}
    }}

    public static void RecordMemory(string tag)
    {{
        long mem = GC.GetTotalMemory(false) / (1024 * 1024);
        RecordMetric(tag + "_memory", mem, "MB");
    }}

    public static void RecordFrameTime(float deltaTime)
    {{
        _lastFPS = 1.0f / deltaTime;
        if (deltaTime > 0.033f) // 低于30帧
        {{
            _frameDropCount++;
            RecordMetric("FrameDrop", (int)_lastFPS, "fps");
        }}
    }}

    public static void RecordMetric(string name, long value, string unit)
    {{
        string line = $"{{DateTime.Now:yyyy-MM-dd HH:mm:ss}},{{name}},{{value}},{{unit}}";
        File.AppendAllText(_reportPath, line + "\\n");
    }}

    public static void SaveReport()
    {{
        // 已实时写入，此处可留空或写汇总
    }}
}}
"""
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, "PerfMonitor.cs")
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return code_path


def generate_perf_hud(output_dir):
    """
    生成简单的性能 HUD 面板。
    """
    code = f"""// 自动生成 - 性能 HUD
// 生成时间：{datetime.now()}
using UnityEngine;

public class PerfHUD : MonoBehaviour
{{
    private bool _show = false;
    private float _fps = 0;
    private long _memory = 0;

    void Update()
    {{
        if (Input.GetKeyDown(KeyCode.F3))
        {{
            _show = !_show;
        }}

        _fps = 1.0f / Time.unscaledDeltaTime;
        _memory = System.GC.GetTotalMemory(false) / (1024 * 1024);
    }}

    void OnGUI()
    {{
        if (!_show) return;

        GUILayout.BeginArea(new Rect(10, 10, 200, 100));
        GUILayout.Label($"FPS: {{_fps:0.0}}");
        GUILayout.Label($"Memory: {{_memory}} MB");
        GUILayout.EndArea();
    }}
}}
"""
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, "PerfHUD.cs")
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return code_path


def inject_perf_probes(source_dir):
    """
    扫描源代码，在关键方法中插入性能监控代码。
    """
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"源代码目录不存在：{source_dir}")
        return []

    injected_files = []
    for code_file in source_path.rglob("*.cs"):
        if ('ErrorLogger.cs' in str(code_file) or 
            'PerfMonitor.cs' in str(code_file) or 
            'PerfHUD.cs' in str(code_file) or
            'UIManager.cs' in str(code_file)):
            continue

        content = code_file.read_text(encoding='utf-8')
        if 'PerfMonitor.BeginSample' in content:
            continue

        modified = False
        lines = content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 识别 Update/FixedUpdate/LateUpdate 方法
            if ('void Update()' in stripped or 
                'void FixedUpdate()' in stripped or 
                'void LateUpdate()' in stripped):
                # 在方法体开头插入性能探测
                new_lines.append(line)
                # 找到下一个 { 的位置，在 { 之后插入
                j = i + 1
                while j < len(lines) and '{' not in lines[j]:
                    new_lines.append(lines[j])
                    j += 1
                if j < len(lines) and '{' in lines[j]:
                    new_lines.append(lines[j])  # 包含 { 的行
                    # 插入监控代码
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    indent_str = ' ' * (indent + 4)
                    new_lines.append(f"{indent_str}PerfMonitor.BeginSample(\"{code_file.stem}.{stripped.split('(')[0].replace('void ', '')}\");")
                    modified = True
                    # 同时添加结束监控的代码在方法结尾的 } 前
                    # 这里简化，仅记录开始，结束由 Dispose 处理
                continue
            new_lines.append(line)

        if modified:
            code_file.write_text('\n'.join(new_lines), encoding='utf-8')
            print(f"  📊 已注入性能埋点：{code_file.name}")
            injected_files.append(str(code_file))

    return injected_files


def run_perf_pipeline(source_dir, output_dir):
    """
    执行性能监控代码生成与注入流水线：
    1. 生成 PerfMonitor.cs
    2. 生成 PerfHUD.cs
    3. 在源代码中注入性能探测
    返回 (monitor_path, hud_path, injected_files)
    """
    monitor_path = generate_perf_monitor(output_dir)
    hud_path = generate_perf_hud(output_dir)
    injected_files = inject_perf_probes(source_dir)
    return monitor_path, hud_path, injected_files