#!/usr/bin/env python3
"""
测试生成与执行工具
识别关键模块，生成最小测试用例，执行并收集结果。
"""

import os
from datetime import datetime
from pathlib import Path
from tools.structured_md import write_data


def load_modules_from_plans(plans_dir):
    """
    从程序计划中识别关键模块。
    读取开发顺序.md 或遍历 Plans 目录，查找标记为关键的计划。
    """
    modules = []
    plans_path = Path(plans_dir)

    # 尝试读取开发顺序
    order_path = plans_path / "开发顺序.md"
    if order_path.exists():
        with open(order_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 简单提取计划ID列表
            for line in content.split('\n'):
                if line.strip().startswith('- 计划列表：'):
                    ids = line.replace('- 计划列表：', '').strip().split(',')
                    for pid in ids:
                        pid = pid.strip()
                        if pid:
                            modules.append({'plan_id': pid, 'name': pid})
    else:
        # 遍历 plans_dir 下的所有 .md 文件
        for md_file in plans_path.rglob('*.md'):
            if md_file.name != '开发顺序.md':
                modules.append({
                    'plan_id': md_file.stem,
                    'name': md_file.stem,
                    'file': str(md_file)
                })

    return modules


def generate_test_for_module(module):
    """
    为一个模块生成测试用例代码（C# 示例）。
    """
    name = module['name'].replace('-', '_').replace(' ', '_')
    test_code = f"""// 自动生成测试用例 - {module['name']}
// 生成时间：{datetime.now()}
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

public class Test{name}
{{
    [SetUp]
    public void Setup()
    {{
        // 初始化测试环境
    }}

    [TearDown]
    public void Teardown()
    {{
        // 清理测试环境
    }}

    // ===== 正常用例 =====
    [Test]
    public void Test_NormalCase_01()
    {{
        // TODO: 验证正确输入产生正确输出
        Assert.Inconclusive("未接入真实断言");
    }}

    [Test]
    public void Test_NormalCase_02()
    {{
        // TODO: 验证典型使用场景
        Assert.Inconclusive("未接入真实断言");
    }}

    // ===== 边界用例 =====
    [Test]
    public void Test_Boundary_ZeroInput()
    {{
        // TODO: 验证输入为0时的行为
        Assert.Inconclusive("未接入真实断言");
    }}

    [Test]
    public void Test_Boundary_NegativeInput()
    {{
        // TODO: 验证输入为负数时的行为
        Assert.Inconclusive("未接入真实断言");
    }}

    [Test]
    public void Test_Boundary_MaxValue()
    {{
        // TODO: 验证输入为最大值时的行为
        Assert.Inconclusive("未接入真实断言");
    }}

    // ===== 异常用例 =====
    [Test]
    public void Test_Exception_NullInput()
    {{
        // TODO: 验证输入为null时的行为（应抛出异常或安全处理）
        Assert.Inconclusive("未接入真实断言");
    }}

    [Test]
    public void Test_Exception_InvalidType()
    {{
        // TODO: 验证输入类型错误时的行为
        Assert.Inconclusive("未接入真实断言");
    }}
}}
"""
    return test_code


def execute_tests_for_module(module, test_dir):
    """
    生成测试文件后不模拟通过结果，等待真实测试运行器接入。
    返回 (passed: bool | None, results: dict)
    """
    results = {
        'module': module['name'],
        'tests_total': 0,
        'passed': 0,
        'failed': 0,
        'status': 'SKIPPED',
        'failures': [],
        'message': '测试用例已生成，未配置真实测试运行器。'
    }
    return None, results


def run_test_pipeline(plans_dir, output_dir):
    """
    完整的测试流水线：
    1. 识别关键模块
    2. 为每个模块生成测试文件
    3. 执行测试
    4. 收集结果并输出报告
    """
    modules = load_modules_from_plans(plans_dir)

    if not modules:
        print("ℹ️ 未检测到需要测试的模块。")
        return None

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    report = {
        'results': [],
        'summary': {}
    }

    all_passed = True

    for module in modules:
        # 生成测试文件
        test_code = generate_test_for_module(module)
        test_file = output_path / f"test_{module['name']}.cs"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
        print(f"📝 测试文件已生成：{test_file}")

        # 执行测试
        passed, result = execute_tests_for_module(module, output_path)
        report['results'].append(result)

        if passed is False:
            all_passed = False

    # 汇总
    total = len(report['results'])
    passed_count = sum(1 for r in report['results'] if r['status'] == 'PASS')
    failed_count = sum(1 for r in report['results'] if r['status'] == 'FAIL')
    skipped_count = sum(1 for r in report['results'] if r['status'] == 'SKIPPED')

    if failed_count > 0:
        overall_status = 'FAIL'
    elif passed_count > 0 and skipped_count == 0:
        overall_status = 'PASS'
    else:
        overall_status = 'SKIPPED'

    report['summary'] = {
        'total_modules': total,
        'passed_modules': passed_count,
        'failed_modules': failed_count,
        'skipped_modules': skipped_count,
        'overall_status': overall_status
    }

    # 如果有失败，添加建议
    if failed_count > 0:
        report['summary']['recommendations'] = [
            "修复失败的测试用例后重新运行测试",
            "检查对应模块的边界条件和异常处理"
        ]

    # 保存报告
    report_file = output_path / "test_results.md"
    write_data(report_file, report, title="Test Results")
    print(f"📊 测试报告已保存：{report_file}")

    return report
