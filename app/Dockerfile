# OpenInterview 后端镜像
FROM python:3.10-slim

# 安装 ffmpeg（Whisper 语音解码依赖）与字体（WeasyPrint 中文 PDF 渲染）
RUN apt-get update && apt-get install -y ffmpeg fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码与静态文件
COPY . .

EXPOSE 8000

RUN chmod +x start.sh
CMD ["./start.sh"]
