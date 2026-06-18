import hashlib
import json
import os


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value):
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def prompt_section_sizes(prompt_payload):
    return {
        key: len(compact_json(value))
        for key, value in prompt_payload.items()
    }


def prompt_replay_fields(prompt_text, preview_limit=2000):
    prompt_text = str(prompt_text or "")
    fields = {
        "packedPromptSha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "packedPromptChars": len(prompt_text),
        "packedPromptPreview": prompt_text[:preview_limit],
    }
    if os.environ.get("AI_INTERVIEW_STORE_FULL_PROMPT") == "1":
        fields["packedPrompt"] = prompt_text
    return fields


def compact_prompt_prefix(prompt_snapshot):
    return "\n".join([
        "以下为当前锁定的 AI 提问提示词框架。它只约束 AI 如何提问、解释、映射和判断置信度；不得修改设计选项框架。",
        f"frameworkVersion: {prompt_snapshot.get('frameworkVersion', '')}",
        f"manifestHash: {prompt_snapshot.get('manifestHash', '')}",
        "规则、项目摘要、候选节点和本轮输出 schema 见下方 JSON；只返回符合 schema 的 JSON。",
    ])


def build_prompt_text(prompt_snapshot, prompt_payload):
    return (
        f"{compact_prompt_prefix(prompt_snapshot)}\n\n"
        "请基于下面 JSON 上下文继续同一个 AI 访谈线程，并只返回符合 output schema 的 JSON。\n\n"
        f"{compact_json(prompt_payload)}"
    )
