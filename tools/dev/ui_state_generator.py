#!/usr/bin/env python3
"""
UI 状态代码生成器
读取 ui_graph.json/ui_graph.md，生成 UIManager.cs 和 UIStateMachine.md。
"""

import os
from datetime import datetime
from pathlib import Path
from tools.structured_md import read_structured_or_text


def load_ui_graph(graph_path):
    return read_structured_or_text(Path(graph_path))


def generate_ui_manager(graph, output_dir, lang='csharp'):
    """
    根据 UI 状态图生成 UIManager 代码。
    """
    panels = graph.get('registry', {}).get('panels', [])
    states = graph.get('graph', {}).get('states', {})
    groups = graph.get('groups', [])

    code = f"""// 自动生成，请勿手动修改
// 生成时间：{datetime.now()}
// 基于 AcuR UI Graph 协议

using System.Collections.Generic;
using UnityEngine;

public class UIManager : MonoBehaviour
{{
    private static UIManager _instance;
    public static UIManager Instance => _instance;

    private Dictionary<string, GameObject> _panels = new Dictionary<string, GameObject>();
    private Stack<string> _popupStack = new Stack<string>();
    private string _currentScreen = null;

    void Awake()
    {{
        if (_instance != null)
        {{
            Destroy(gameObject);
            return;
        }}
        _instance = this;
        DontDestroyOnLoad(gameObject);
    }}

    public void RegisterPanel(string id, GameObject panel)
    {{
        if (!_panels.ContainsKey(id))
        {{
            _panels[id] = panel;
            panel.SetActive(false);
        }}
    }}

    public void OpenPanel(string id)
    {{
        if (!_panels.ContainsKey(id))
        {{
            Debug.LogError($"UIManager: 未注册的面板 {{id}}");
            return;
        }}

        var panel = _panels[id];
        var state = GetState(id);

        // 处理独占层互斥
        if (state != null && state.TryGetValue("layer", out var layer))
        {{
            foreach (var g in GetGroups())
            {{
                if (g["name"] == layer.ToString())
                {{
                    foreach (var otherId in g["panels"])
                    {{
                        if (otherId != id && _panels.ContainsKey(otherId))
                        {{
                            _panels[otherId].SetActive(false);
                        }}
                    }}
                }}
            }}
        }}

        panel.SetActive(true);

        // 记录当前屏幕
        if (state != null && state.TryGetValue("layer", out var l) && l.ToString() == "Screen")
        {{
            _currentScreen = id;
        }}

        // 处理弹出栈
        if (state != null && state.TryGetValue("popup_policy", out var policy) && policy != null)
        {{
            _popupStack.Push(id);
        }}

        // 输入锁定
        if (state != null && state.TryGetValue("input_mode", out var mode) && mode.ToString() == "ui_only")
        {{
            LockGameInput(true);
        }}
    }}

    public void ClosePanel(string id)
    {{
        if (!_panels.ContainsKey(id)) return;
        _panels[id].SetActive(false);
        LockGameInput(false);
    }}

    public void CloseTopPopup()
    {{
        if (_popupStack.Count > 0)
        {{
            var id = _popupStack.Pop();
            ClosePanel(id);
        }}
    }}

    private void LockGameInput(bool locked)
    {{
        // 实现游戏输入锁定逻辑
        Time.timeScale = locked ? 0f : 1f;
    }}

    private Dictionary<string, object> GetState(string id)
    {{
        // 简化：直接返回空，实际应存储状态定义
        return null;
    }}

    private List<Dictionary<string, object>> GetGroups()
    {{
        return new List<Dictionary<string, object>>();
    }}
}}
"""
    os.makedirs(output_dir, exist_ok=True)
    code_path = os.path.join(output_dir, "UIManager.cs")
    with open(code_path, 'w', encoding='utf-8') as f:
        f.write(code)
    return code_path


def generate_state_doc(graph, output_dir):
    """
    生成人类可读的状态迁移文档。
    """
    states = graph.get('graph', {}).get('states', {})
    layers = graph.get('layers', [])

    doc = f"""# UI 状态迁移文档

生成时间：{datetime.now()}

## 层级定义

| 层级 | 顺序 | 独占 |
|------|------|------|
"""
    for layer in layers:
        exclusive = "是" if layer.get('exclusive') else "否"
        doc += f"| {layer['id']} | {layer.get('order', '-')} | {exclusive} |\n"

    doc += "\n## 状态迁移表\n\n"
    doc += "| 状态 ID | 层级 | 输入模式 | 迁移目标 |\n"
    doc += "|---------|------|----------|----------|\n"

    for state_id, state in states.items():
        layer = state.get('layer', '-')
        input_mode = state.get('input_mode', '-')
        transitions = state.get('transitions', [])
        targets = ', '.join([f"{t['to']}({t['type']})" for t in transitions]) if transitions else '-'
        doc += f"| {state_id} | {layer} | {input_mode} | {targets} |\n"

    os.makedirs(output_dir, exist_ok=True)
    doc_path = os.path.join(output_dir, "UIStateMachine.md")
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return doc_path


if __name__ == "__main__":
    # 示例：python ui_state_generator.py
    BASE_DIR = Path(__file__).parent.parent
    graph_path = BASE_DIR / "source_artifacts" / "ui_graph.json"
    if not graph_path.exists():
        graph_path = BASE_DIR / "source_artifacts" / "ui_graph.md"
    output_dir = BASE_DIR / "outputs" / "runtime" / "ui"

    if graph_path.exists():
        graph = load_ui_graph(graph_path)
        code_path = generate_ui_manager(graph, output_dir)
        doc_path = generate_state_doc(graph, output_dir)
        print(f"✅ UIManager 已生成：{code_path}")
        print(f"✅ 状态文档已生成：{doc_path}")
    else:
        print("ui_graph.json/ui_graph.md 未找到，跳过 UI 代码生成。")
