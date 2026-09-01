"""
OpenInterview - LLM 服务层

通过 OpenAI 兼容接口调用大模型，支持 GLM / OpenAI / DeepSeek / Moonshot 等。
统一在此层处理：客户端初始化、JSON 输出解析、失败重试与容错。
"""
import json
import re

from openai import OpenAI

from config import config


def _get_client() -> OpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "未配置 LLM API 密钥：请复制 .env.example 为 .env 并填入 OPENAI_API_KEY"
        )
    return OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)


def _extract_json(text: str) -> dict:
    """从模型输出中稳健地提取 JSON 对象（兼容 markdown 代码块包裹的情况）"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)


def chat_json(system_prompt: str, user_prompt: str) -> dict:
    """
    调用 LLM 并要求返回 JSON 对象。
    失败时抛出异常，由调用方决定容错策略。
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        stream=False,
    )
    content = response.choices[0].message.content
    return _extract_json(content)
