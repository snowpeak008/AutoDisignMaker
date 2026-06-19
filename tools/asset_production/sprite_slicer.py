import os
from PIL import Image
from core.utils.base_tool import BaseTool

class SpriteSheetSlicer(BaseTool):
    name: str = "Sprite Sheet Slicer"
    description: str = "按网格切割图集，保存到指定目录。"

    def _run(self, sheet_path: str, output_dir: str,
             grid: str = "5x4", cell_size: str = "128x128", gap: int = 4) -> str:
        try:
            cols, rows = map(int, grid.split("x"))
            cw, ch = map(int, cell_size.split("x"))
            img = Image.open(sheet_path)
            os.makedirs(output_dir, exist_ok=True)
            saved = []
            for r in range(rows):
                for c in range(cols):
                    x = c * (cw + gap)
                    y = r * (ch + gap)
                    crop = img.crop((x, y, x + cw, y + ch))
                    fname = f"icon_{r:02d}_{c:02d}.png"
                    fpath = os.path.join(output_dir, fname)
                    crop.save(fpath, "PNG")
                    saved.append(fpath)
            return f"切割完成，共 {len(saved)} 个文件。"
        except Exception as e:
            return f"切割失败：{str(e)}"
