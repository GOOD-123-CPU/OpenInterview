"""
OpenInterview - LLM 服务层

通过 OpenAI 兼容接口调用大模型，支持 GLM / OpenAI / DeepSeek / Moonshot 等。
统一在此层处理：客户端初始化、指数退避重试、超时控制、JSON 输出解析、失败容错。
"""
import json
import random
import re
import time

from openai import OpenAI

from config import config

# 重试与超时参数
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 120

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """获取（懒加载单例的）OpenAI 兼容客户端"""
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise RuntimeError(
                "未配置 LLM API 密钥：请复制 .env.example 为 .env 并填入 OPENAI_API_KEY"
            )
        _client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=0,  # 重试逻辑自管（带指数退避）
        )
    return _client


def _extract_json(text: str) -> dict:
    """从模型输出中稳健地提取 JSON 对象（兼容 markdown 代码块包裹的情况）"""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # 尝试截取首个 { 或 [ 到最后一个 } 或 ] 之间的内容
    start = min(
        (i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1
    )
    if start > 0:
        text = text[start:]
    return json.loads(text)


def chat_json(system_prompt: str, user_prompt: str) -> dict:
    """
    调用 LLM 并要求返回 JSON 对象。
    网络抖动/限流时按指数退避自动重试；最终失败抛出异常，由调用方容错。
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = get_client().chat.completions.create(
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
        except Exception as e:  # noqa: BLE001 - LLM SDK 异常类型多，统一重试
            last_error = e
            if attempt < MAX_RETRIES:
                backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(f"[llm] 第 {attempt} 次调用失败: {e}，{backoff:.1f}s 后重试")
                time.sleep(backoff)
    raise RuntimeError(f"LLM 调用在 {MAX_RETRIES} 次尝试后仍失败: {last_error}") from last_error
