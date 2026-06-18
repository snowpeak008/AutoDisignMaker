import json
from datetime import datetime
from pathlib import Path

from design_tool.data_loader import data_dir, load_domains, load_templates


SCHEMA_VERSION = "0.5.0"


def checklist_path(domain_id, node_id, item_id):
    return f"{domain_id}.{node_id}.{item_id}"


def build_option_mapping(domains=None):
    domains = domains or load_domains()
    mapped_domains = []
    for domain_doc in domains:
        domain = domain_doc["domain"]
        domain_id = domain["id"]
        nodes = []
        for node in domain_doc.get("nodes", []):
            checklist = []
            for item in node.get("checklist", []):
                checklist.append({
                    "id": item["id"],
                    "label": item["label"],
                    "description": item.get("description", ""),
                    "outputKey": item.get("outputKey", ""),
                    "legacyIds": item.get("legacyIds", []),
                    "templateRef": item.get("templateRef", ""),
                    "path": checklist_path(domain_id, node["id"], item["id"]),
                    "optionRelations": [
                        {
                            "id": relation.get("id", ""),
                            "type": relation.get("type", ""),
                            "severity": relation.get("severity", "warning"),
                            "reason": relation.get("reason", ""),
                            "source": relation.get("source", {}),
                            "targets": relation.get("targets", []),
                        }
                        for relation in item.get("optionRelations", [])
                    ],
                    "optionGroups": [
                        {
                            "id": group["id"],
                            "label": group["label"],
                            "description": group.get("description", ""),
                            "outputKey": group.get("outputKey", ""),
                            "selectionMode": group.get("selectionMode", "multi"),
                            "required": bool(group.get("required", False)),
                            "allowPrimary": bool(group.get("allowPrimary", False)),
                            "mdaLayer": group.get("mdaLayer", ""),
                            "mdaLayerLabel": group.get("mdaLayerLabel", ""),
                            "progressionStep": group.get("progressionStep", 0),
                            "relation": group.get("relation", ""),
                            "designQuestion": group.get("designQuestion", ""),
                            "path": f"{checklist_path(domain_id, node['id'], item['id'])}.{group['id']}",
                            "options": [
                                {
                                    "id": option["id"],
                                    "label": option["label"],
                                    "description": option.get("description", ""),
                                    "outputKey": option.get("outputKey", ""),
                                    "path": f"{checklist_path(domain_id, node['id'], item['id'])}.{group['id']}.{option['id']}",
                                }
                                for option in group.get("options", [])
                            ],
                        }
                        for group in item.get("optionGroups", [])
                    ],
                })
            nodes.append({
                "id": node["id"],
                "name": node["name"],
                "description": node.get("description", ""),
                "checklist": checklist,
            })
        mapped_domains.append({
            "id": domain_id,
            "name": domain["name"],
            "description": domain.get("description", ""),
            "nodes": nodes,
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "generatedFrom": "new_tools/data/domains",
        "templates": [
            {
                "id": template.get("id", template_id),
                "name": template.get("name", template_id),
                "description": template.get("description", ""),
                "optionGroupIds": [group.get("id", "") for group in template.get("optionGroups", [])],
            }
            for template_id, template in sorted(load_templates().items())
        ],
        "domains": mapped_domains,
    }


def markdown_escape(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_mapping_markdown(mapping):
    lines = [
        "# 选项描述映射",
        "",
        f"- schemaVersion: `{mapping['schemaVersion']}`",
        f"- generatedFrom: `{mapping['generatedFrom']}`",
        f"- generatedAt: `{mapping['generatedAt']}`",
        "",
    ]
    if mapping.get("templates"):
        lines.extend(["## 共享模板", ""])
        for template in mapping.get("templates", []):
            lines.extend([
                f"### {markdown_escape(template.get('name', template.get('id', '')))}",
                "",
                f"- templateRef: `{markdown_escape(template.get('id', ''))}`",
                f"- optionGroups: {', '.join(f'`{markdown_escape(group_id)}`' for group_id in template.get('optionGroupIds', []))}",
                "",
                markdown_escape(template.get("description", "")),
                "",
            ])
    for domain in mapping["domains"]:
        lines.extend([
            f"## {domain['name']}",
            "",
            domain.get("description", ""),
            "",
        ])
        for node in domain.get("nodes", []):
            lines.extend([
                f"### {node['name']}",
                "",
                node.get("description", ""),
                "",
                "| 选项 | 稳定 ID | 结构字段 | 完整路径 | 简短描述 |",
                "| --- | --- | --- | --- | --- |",
            ])
            for item in node.get("checklist", []):
                lines.append(
                    "| "
                    + " | ".join([
                        markdown_escape(item["label"]),
                        f"`{markdown_escape(item['id'])}`",
                        f"`{markdown_escape(item['outputKey'])}`",
                        f"`{markdown_escape(item['path'])}`",
                        markdown_escape(item.get("description", "")),
                    ])
                    + " |"
                )
                if item.get("templateRef"):
                    lines.append("")
                    lines.append(f"> templateRef: `{markdown_escape(item['templateRef'])}` — 本 checklist 采用共享元模板,具体内容需在 L5 补充。")
                for group in item.get("optionGroups", []):
                    required = "必选" if group.get("required") else "可选"
                    primary = "可标主目标" if group.get("allowPrimary") else "不标主目标"
                    lines.append("")
                    lines.append(f"#### {item['label']} / {group['label']}")
                    lines.append("")
                    if group.get("description"):
                        lines.append(group["description"])
                        lines.append("")
                    lines.extend([
                        f"- groupId: `{group['id']}`",
                        f"- outputKey: `{group['outputKey']}`",
                        f"- progressionStep: `{group.get('progressionStep', 0)}`",
                        f"- mdaLayer: `{group.get('mdaLayer', '')}` {markdown_escape(group.get('mdaLayerLabel', ''))}",
                        f"- relation: `{markdown_escape(group.get('relation', ''))}`",
                        f"- selectionMode: `{group.get('selectionMode', 'multi')}`",
                        f"- requirement: {required}，{primary}",
                        "",
                    ])
                    if group.get("designQuestion"):
                        lines.extend([
                            f"设计问题：{markdown_escape(group['designQuestion'])}",
                            "",
                        ])
                    lines.extend([
                        "| 选项 | 稳定 ID | 结构字段 | 完整路径 | 简短描述 |",
                        "| --- | --- | --- | --- | --- |",
                    ])
                    for option in group.get("options", []):
                        lines.append(
                            "| "
                            + " | ".join([
                                markdown_escape(option["label"]),
                                f"`{markdown_escape(option['id'])}`",
                                f"`{markdown_escape(option['outputKey'])}`",
                                f"`{markdown_escape(option['path'])}`",
                                markdown_escape(option.get("description", "")),
                            ])
                            + " |"
                        )
                if item.get("optionRelations"):
                    lines.extend([
                        "",
                        f"#### {item['label']} / 选项关系",
                        "",
                        "| 类型 | 来源 | 目标 | 原因 |",
                        "| --- | --- | --- | --- |",
                    ])
                    for relation in item.get("optionRelations", []):
                        source = relation.get("source", {})
                        source_text = f"`{source.get('groupId', '')}.{source.get('optionId', '')}`"
                        targets = "，".join(
                            f"`{target.get('groupId', '')}.{target.get('optionId', '')}`"
                            for target in relation.get("targets", [])
                        )
                        lines.append(
                            "| "
                            + " | ".join([
                                markdown_escape(relation.get("type", "")),
                                source_text,
                                targets,
                                markdown_escape(relation.get("reason", "")),
                            ])
                            + " |"
                        )
            lines.append("")
    return "\n".join(lines)


def write_option_mapping(target_dir=None, domains=None):
    target = Path(target_dir) if target_dir else data_dir()
    target.mkdir(parents=True, exist_ok=True)
    mapping = build_option_mapping(domains)
    json_path = target / "option_mapping.json"
    md_path = target / "option_mapping.md"
    json_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_mapping_markdown(mapping), encoding="utf-8")
    return md_path, json_path


def main():
    md_path, json_path = write_option_mapping()
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
