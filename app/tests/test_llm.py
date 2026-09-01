"""
OpenInterview - LLM 服务 JSON 解析单元测试（不发起真实网络请求）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.llm import _extract_json


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_wrapped(self):
        text = '```json\n{"questions": [{"q": "hi"}]}\n```'
        assert _extract_json(text) == {"questions": [{"q": "hi"}]}

    def test_prefix_noise(self):
        text = '好的，以下是结果：\n{"ok": true}'
        assert _extract_json(text) == {"ok": True}

    def test_invalid_raises(self):
        with pytest.raises(Exception):
            _extract_json("这不是 JSON")
