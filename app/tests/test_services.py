"""
OpenInterview - 服务层单元测试

覆盖：报告评分离散化、雷达图渲染、简历解析降级、提示词注册表。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestReportClamping:
    """评分离散化：非法输入必须被钳制，绝不能把 NaN/字符串写进报告"""

    def test_clamp_score_normal(self):
        from services.report_service import _clamp_score

        assert _clamp_score(85) == 85
        assert _clamp_score("92.7") == 92
        assert _clamp_score(0) == 0
        assert _clamp_score(100) == 100

    def test_clamp_score_out_of_range(self):
        from services.report_service import _clamp_score

        assert _clamp_score(-5) == 0
        assert _clamp_score(150) == 100
        assert _clamp_score(999) == 100

    def test_clamp_score_invalid(self):
        from services.report_service import _clamp_score

        assert _clamp_score(None) is None
        assert _clamp_score("abc") is None
        assert _clamp_score("") is None


class TestRadarRenderer:
    def test_basic_render(self):
        from services.radar import render_radar_svg

        svg = render_radar_svg({"technical": 85, "project": 70, "design": 60, "behavior": 90})
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        # 数据点应为 4 个
        assert svg.count("<circle") == 4
        # 数值标注存在
        assert ">85</text>" in svg and ">90</text>" in svg

    def test_missing_dimensions_default_zero(self):
        from services.radar import render_radar_svg

        svg = render_radar_svg({})  # 全缺省
        assert svg.count("<circle") == 4
        assert ">0</text>" in svg

    def test_scores_clamped_in_svg(self):
        from services.radar import render_radar_svg

        svg = render_radar_svg({"technical": 500, "project": -20})  # 越界输入
        assert ">100</text>" in svg  # 500 → 100
        assert ">0</text>" in svg    # -20 → 0

    def test_no_nan_in_output(self):
        from services.radar import render_radar_svg

        svg = render_radar_svg({"technical": None, "project": "bad"})
        # 检查所有数值标注文本（<text>…</text> 内容）不含 nan/inf
        import re

        text_values = re.findall(r"font-weight=\"bold\">([^<]+)</text>", svg)
        assert all(v.isdigit() for v in text_values), f"数值标注异常: {text_values}"


class TestResumeParser:
    def test_none_and_empty(self):
        from services.resume import extract_text_from_resume

        assert extract_text_from_resume(None) == "无简历内容"
        assert extract_text_from_resume(b"") == "无简历内容"

    def test_plain_text_fallback(self):
        from services.resume import extract_text_from_resume

        # 非 PDF 二进制 → 降级为文本
        text = extract_text_from_resume("Python 工程师，5 年经验".encode())
        assert "Python" in text

    def test_invalid_pdf_returns_string_not_crash(self):
        from services.resume import extract_text_from_resume

        text = extract_text_from_resume(b"%PDF-1.4 garbage-not-really-pdf")
        assert isinstance(text, str) and text


class TestPromptRegistry:
    def test_yaml_loads_and_versions(self):
        from prompt_registry import list_prompts

        prompts = list_prompts()
        names = {p["name"] for p in prompts}
        assert {"question_generation", "report_evaluation"} <= names
        for p in prompts:
            assert p["version"] != "?"

    def test_render_prompt_variables(self):
        from prompt_registry import render_prompt

        system, user = render_prompt(
            "question_generation",
            position_name="后端", requirements="Python",
            responsibilities="开发", resume_text="张三的简历",
            question_count=10, format_example="[]",
        )
        assert "面试官" in system
        assert "后端" in user and "张三的简历" in user
        assert "{position_name}" not in user  # 变量已全部替换

    def test_missing_variable_raises_early(self):
        from prompt_registry import render_prompt

        with pytest.raises(KeyError):
            render_prompt("question_generation", position_name="x")  # 缺一堆变量

    def test_unknown_prompt_raises(self):
        from prompt_registry import get_prompt

        with pytest.raises(KeyError):
            get_prompt("no_such_prompt")
