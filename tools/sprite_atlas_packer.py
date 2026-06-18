#!/usr/bin/env python3
"""
序列帧图集自动打包工具
根据任务描述自动生成多帧图片，拼成图集，输出元数据文件。
"""

import os
import json
import time
from PIL import Image
from tools.base_tool import BaseTool
from tools.image2_tool import Image2Generator
from tools.sprite_slicer import SpriteSheetSlicer


class SpriteAtlasPacker(BaseTool):
    name: str = "Sprite Atlas Packer"
    description: str = (
        "自动完成序列帧生成、切割、拼图集、输出元数据全流程。"
        "参数：prompt（描述），frame_count（帧数），output_dir（输出目录），"
        "atlas_name（图集名称），cell_size（单帧尺寸如128x128）"
    )

    def _run(self, prompt: str, frame_count: int = 8,
             output_dir: str = "ArtAssets/Animations",
             atlas_name: str = "animation",
             cell_size: str = "128x128") -> str:
        try:
            os.makedirs(output_dir, exist_ok=True)

            # 1. 逐帧生成图片
            generator = Image2Generator()
            frame_paths = []
            for i in range(frame_count):
                frame_prompt = f"{prompt}, frame {i+1} of {frame_count}"
                result = generator._run(prompt=frame_prompt, output_dir=output_dir,
                                       size=cell_size, output_format="png")
                # 提取文件路径（generator 返回 "图片已保存至：xxx"）
                if "： " in result:
                    path = result.split("： ")[-1].strip()
                elif "：" in result:
                    path = result.split("：")[-1].strip()
                else:
                    path = result
                frame_paths.append(path)
                time.sleep(0.5)  # 避免 API 调用太快

            # 2. 拼成图集
            cols = int(frame_count ** 0.5) if frame_count > 1 else 1
            rows = (frame_count + cols - 1) // cols
            cw, ch = map(int, cell_size.split('x'))

            atlas_width = cols * cw
            atlas_height = rows * ch
            atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))

            metadata = {
                "atlas": f"{atlas_name}.png",
                "cell_size": [cw, ch],
                "frames": []
            }

            for idx, frame_path in enumerate(frame_paths):
                col = idx % cols
                row = idx // cols
                x = col * cw
                y = row * ch

                frame_img = Image.open(frame_path).convert("RGBA")
                frame_img = frame_img.resize((cw, ch), Image.LANCZOS)
                atlas.paste(frame_img, (x, y))

                metadata["frames"].append({
                    "index": idx,
                    "x": x,
                    "y": y,
                    "width": cw,
                    "height": ch,
                    "source": os.path.basename(frame_path)
                })

            # 3. 保存图集和元数据
            atlas_path = os.path.join(output_dir, f"{atlas_name}.png")
            atlas.save(atlas_path, "PNG")

            meta_path = os.path.join(output_dir, f"{atlas_name}.json")
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            return (
                f"图集已生成：{atlas_path}\n"
                f"元数据：{meta_path}\n"
                f"共 {frame_count} 帧，排列 {cols}x{rows}"
            )

        except Exception as e:
            return f"图集打包失败：{str(e)}"
