"""
OpenInterview - 雷达图渲染器

纯 Python 生成 SVG 雷达图（零前端依赖），嵌入 PDF 报告。
WeasyPrint 支持 SVG 渲染，无需额外图像库。
"""
import math

# 维度顺序固定（报告模板与数据键一致）
DIMENSIONS = [
    ("technical", "技术深度"),
    ("project", "项目复盘"),
    ("design", "系统设计"),
    ("behavior", "行为素质"),
]

_SIZE = 220  # 画布边长
_CENTER = _SIZE // 2
_RADIUS = 80
_LEVELS = 4  # 同心网格层数


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg - 90)  # 顶部为 0 度
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _safe_score(value) -> int:
    """任意输入 → 0-100 整数；无法解析按 0 处理"""
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


def render_radar_svg(scores: dict, size: int = _SIZE) -> str:
    """
    渲染四维雷达图 SVG。

    scores: {"technical": 85, "project": 80, ...}，缺省维度按 0 处理。
    返回 SVG 字符串（可直接嵌入 HTML）。
    """
    n = len(DIMENSIONS)
    angle_step = 360 / n
    cx, cy, r = size / 2, size / 2 + 4, _RADIUS * size / _SIZE

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size + 8}" '
        f'width="{size}" height="{size + 8}">'
    ]

    # 同心网格（菱形）
    for level in range(1, _LEVELS + 1):
        lr = r * level / _LEVELS
        pts = " ".join(
            f"{x:.1f},{y:.1f}" for x, y in
            (_polar(cx, cy, lr, i * angle_step) for i in range(n))
        )
        parts.append(
            f'<polygon points="{pts}" fill="none" stroke="#d5d5d5" stroke-width="1"/>'
        )

    # 轴线 + 标签
    for i, (_, label) in enumerate(DIMENSIONS):
        x, y = _polar(cx, cy, r, i * angle_step)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d5d5d5" stroke-width="1"/>')
        lx, ly = _polar(cx, cy, r + 22, i * angle_step)
        anchor = "middle"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="12" fill="#555" dominant-baseline="middle">{label}</text>'
        )

    # 数据多边形
    points = []
    for i, (key, _) in enumerate(DIMENSIONS):
        score = _safe_score(scores.get(key))
        points.append(_polar(cx, cy, r * score / 100, i * angle_step))
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    parts.append(
        f'<polygon points="{pts_str}" fill="rgba(47,107,255,0.25)" '
        f'stroke="#2f6bff" stroke-width="2"/>'
    )
    for x, y in points:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#2f6bff"/>')

    # 数值标注
    for i, (key, _) in enumerate(DIMENSIONS):
        score = _safe_score(scores.get(key))
        nx, ny = _polar(cx, cy, r * score / 100 + 14, i * angle_step)
        parts.append(
            f'<text x="{nx:.1f}" y="{ny:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#2f6bff" font-weight="bold">{score}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)
