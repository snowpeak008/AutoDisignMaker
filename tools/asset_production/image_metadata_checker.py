import os
from PIL import Image
from core.utils.base_tool import BaseTool

class ImageMetadataChecker(BaseTool):
    name: str = "Image Metadata Checker"
    description: str = "检查图片尺寸、格式等元数据是否符合预期。"

    def _run(self, filepath: str, expected_width: int = 0,
             expected_height: int = 0, expected_format: str = "PNG") -> str:
        try:
            if not os.path.exists(filepath):
                return f"FAIL: 文件不存在 {filepath}"
            img = Image.open(filepath)
            w, h = img.size
            fmt = img.format
            issues = []
            if expected_width and w != expected_width:
                issues.append(f"宽度不符：期望 {expected_width}，实际 {w}")
            if expected_height and h != expected_height:
                issues.append(f"高度不符：期望 {expected_height}，实际 {h}")
            if expected_format and fmt.upper() != expected_format.upper():
                issues.append(f"格式不符：期望 {expected_format}，实际 {fmt}")
            return "PASS" if not issues else f"FAIL: {'; '.join(issues)}"
        except Exception as e:
            return f"FAIL: 无法打开图片 - {str(e)}"
