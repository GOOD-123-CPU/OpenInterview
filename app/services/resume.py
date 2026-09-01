"""
OpenInterview - 简历解析服务层

从二进制简历内容中提取文本，供 LLM 生成面试问题使用。
当前支持 PDF（PyPDF2）；解析失败时降级为纯文本尝试，保证流程不中断。
"""
import io

import PyPDF2


def extract_text_from_resume(pdf_content) -> str:
    """从 PDF 二进制数据提取文本；失败时降级尝试纯文本"""
    if pdf_content is None or pdf_content == b"":
        return "无简历内容"

    # 首选：PDF 解析
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = PyPDF2.PdfReader(pdf_file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"[resume] PDF 解析失败: {e}")

    # 降级：按纯文本处理
    try:
        if isinstance(pdf_content, bytes):
            decoded = pdf_content.decode("utf-8", errors="ignore")
            if decoded.strip():
                return decoded.strip()
        return str(pdf_content)
    except Exception:
        return "无法解析简历内容"
