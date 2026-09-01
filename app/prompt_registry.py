"""
OpenInterview - 提示词注册表

所有 LLM 提示词集中于 prompts.yaml 版本化管理：
- 修改提示词不需要动代码，递增 version 即可追溯
- 提供 list_prompts() 供 CLI 审查当前生效的提示词版本
"""
from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_FILE = Path(__file__).parent / "prompts.yaml"


@lru_cache(maxsize=1)
def _load_prompts() -> dict:
    """加载提示词注册表（进程内缓存；CLI 可传 force 刷新）"""
    if not _PROMPTS_FILE.exists():
        raise FileNotFoundError(f"提示词注册表不存在: {_PROMPTS_FILE}")
    with open(_PROMPTS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_prompt(name: str) -> dict:
    """获取指定提示词的 {"system", "user", "version"}；不存在抛 KeyError"""
    prompts = _load_prompts()
    if name not in prompts:
        raise KeyError(f"提示词不存在: {name}，可用: {', '.join(prompts)}")
    entry = prompts[name]
    return {
        "system": entry["system"],
        "user": entry["user"],
        "version": entry.get("version", "unknown"),
    }


def render_prompt(name: str, **variables) -> tuple[str, str]:
    """渲染提示词，返回 (system, user)。缺失变量会抛 KeyError，尽早暴露问题"""
    prompt = get_prompt(name)
    return prompt["system"], prompt["user"].format(**variables)


def list_prompts() -> list[dict]:
    """列出全部提示词及其版本（CLI 审查用）"""
    prompts = _load_prompts()
    return [
        {"name": name, "version": entry.get("version", "?"), "description": entry.get("description", "")}
        for name, entry in prompts.items()
    ]


# 供 CI / 测试验证 YAML 合法性
if __name__ == "__main__":
    for p in list_prompts():
        print(f"{p['name']}@{p['version']}: {p['description']}")
