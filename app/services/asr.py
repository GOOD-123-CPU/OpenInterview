"""
OpenInterview - 语音转写服务层

封装 Whisper 模型的加载与转写：
- GPU 可用时使用可配置的大模型，否则回退到轻量模型
- 统一处理临时音频文件（前端 MediaRecorder 一般输出 webm/ogg，Whisper + ffmpeg 可直接解析）
"""
import tempfile

import torch
import whisper

from config import config

_whisper_model = None


def load_whisper_model():
    """按需懒加载 Whisper 模型（首次调用时初始化，避免 import 副作用）"""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    if torch.cuda.is_available():
        print(f"[asr] GPU 可用，加载 {config.WHISPER_MODEL_GPU} 模型")
        _whisper_model = whisper.load_model(config.WHISPER_MODEL_GPU).to("cuda")
    else:
        print(f"[asr] GPU 不可用，加载 {config.WHISPER_MODEL_CPU} 模型")
        _whisper_model = whisper.load_model(config.WHISPER_MODEL_CPU)
    return _whisper_model


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    将音频二进制内容转写为中文文本。

    说明：不依赖扩展名猜测，统一写入 .webm 临时文件——
    Whisper 底层经 ffmpeg 解码，webm/ogg/wav/mp3 等常见格式均可正确处理。
    """
    model = load_whisper_model()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        result = model.transcribe(tmp_path, language="zh")
        return (result.get("text") or "").strip()
    finally:
        if tmp_path:
            import contextlib
            import os

            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
