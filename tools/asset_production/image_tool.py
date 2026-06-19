import os
import json
import time
import base64
import requests
from core.utils.base_tool import BaseTool
from tools.config_loader import get_api_config, openai_endpoint


class Image2Generator(BaseTool):
    name: str = "IMAGE2 Generator"
    description: str = "调用中转平台 IMAGE2 /v1/responses API 生成图片，返回文件路径。"

    def _run(self, prompt: str, output_dir: str = "GeneratedAssets",
             size: str = "1024x1024", quality: str = "high",
             output_format: str = "png") -> str:
        # 从统一配置获取 IMAGE2 的密钥与地址
        img_cfg = get_api_config("image2")
        api_base = img_cfg["base_url"]
        api_key = img_cfg["api_key"]

        payload = {
            "model": "gpt-5.5",
            "stream": True,
            "tool_choice": "auto",
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "tools": [{
                "type": "image_generation",
                "model": "gpt-image-2",
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "background": "opaque"
            }]
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(openai_endpoint(api_base, "responses"), json=payload, headers=headers,
                                 stream=True, timeout=300)
            final_b64 = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                    if event.get("type") == "response.output_item.done":
                        item = event.get("item", {})
                        if item.get("type") == "image_generation_call" and item.get("result"):
                            final_b64 = item["result"]
                    elif event.get("type") == "response.completed":
                        for out in event.get("response", {}).get("output", []):
                            if out.get("type") == "image_generation_call" and out.get("result"):
                                final_b64 = out["result"]
                except Exception:
                    continue
            if not final_b64:
                return "错误：未提取到最终图片。"
            img_bytes = base64.b64decode(final_b64)
            os.makedirs(output_dir, exist_ok=True)
            fname = f"img_{int(time.time())}.{output_format}"
            path = os.path.join(output_dir, fname)
            with open(path, "wb") as f:
                f.write(img_bytes)
            return f"图片已保存至：{path}"
        except Exception as e:
            return f"IMAGE2 生成失败：{str(e)}"
