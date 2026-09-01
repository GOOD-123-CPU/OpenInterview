# OpenInterview · AI 智能面试系统

[中文](#中文说明) | [English](#english)

---

<a id="中文说明"></a>

> 基于 LLM（GLM / OpenAI / DeepSeek 等兼容接口）与 Whisper 语音识别的自动化面试系统：根据候选人简历与岗位需求自动生成面试题，候选人在线语音作答，系统自动转录并生成结构化 PDF 评估报告。

## 功能特性

- **智能出题** — 结合岗位 JD 与候选人 PDF 简历，由大模型生成针对性面试问题（含评分标准）
- **在线语音面试** — 候选人通过专属链接进入面试页，浏览器录音作答，支持题目语音朗读（可开关）
- **自动评估报告** — 面试完成后自动转录、评分并渲染为 PDF 报告（技术/沟通/综合分 + 逐题点评）
- **完整招聘管理** — 岗位、候选人、面试三合一管理后台
- **定时自动处理** — 后台 worker 周期扫描并处理待出题 / 待评估的面试
- **一键部署** — Docker Compose 一条命令拉起全部服务

## 系统架构

```
┌─────────────┐     ┌──────────────────────────────────────┐
│  浏览器      │     │            Flask 后端 (:8000)         │
│  管理后台    │────▶│  api/        岗位·候选人·面试 REST API │
│  面试页面    │────▶│  services/   LLM·Whisper·简历解析      │
└─────────────┘     │  tasks/      出题·报告 定时 worker     │
                    └──────────────┬───────────────────────┘
                                   ▼
                          SQLite (interview_system.db)
```

**面试状态机**：`0 未开始 → 1 试题已备好 → 2 进行中 → 3 面试完毕 → 4 报告已生成`

## 快速开始

### 方式一：Docker（推荐）

```bash
# 1. 配置环境变量
cp app/.env.example app/.env
#    编辑 app/.env，填入你的 OPENAI_API_KEY 等

# 2. 启动
docker compose up --build -d

# 3. 访问
#    管理后台  http://localhost:8000/static/admin.html
```

### 方式二：本地运行

```bash
cd app

# 1. 创建虚拟环境并安装依赖（Python 3.10+）
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / macOS
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env             # 填入你的 API Key

# 3. 初始化数据库（也可跳过，server 启动时会自动建表）
python database.py

# 4. 分别启动三个服务（三个终端）
python server.py                    # Web API（必须）
python tasks/question_worker.py     # 出题 worker
python tasks/report_worker.py      # 报告 worker
```

> **依赖提示**
> - Whisper 依赖 **ffmpeg**：Windows 安装见 [docs/legacy/Windows 上安装 FFmpeg 指南.md](docs/legacy/Windows%20上安装%20FFmpeg%20指南.md)，macOS `brew install ffmpeg`
> - PDF 生成依赖 **WeasyPrint**：Windows 需安装 GTK 运行时，见 [docs/legacy/Windows上安装gtk.md](docs/legacy/Windows上安装gtk.md)
> - 有 NVIDIA GPU 时自动使用 `WHISPER_MODEL_GPU` 指定的模型，否则回退 CPU 模型

## 使用流程

1. 打开管理后台 → **岗位管理** → 添加岗位（名称 / 要求 / 职责）
2. **候选人管理** → 添加候选人并上传 PDF 简历
3. **面试管理** → 创建面试（出题 worker 会在下个周期自动生成题目，状态变为「试题已备好」）
4. 点击 **复制面试链接**，发给候选人
5. 候选人打开链接 → 开始面试 → 逐题语音作答（可开启题目朗读）
6. 全部作答完毕 → 报告 worker 自动生成 PDF → 管理端点击 **下载面试报告**

## 配置项

所有配置通过环境变量 / `.env` 管理，详见 [`app/.env.example`](app/.env.example)：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API 密钥（必填） | — |
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址 | 智谱 GLM |
| `LLM_MODEL` | 模型名 | `glm-4-plus` |
| `PUBLIC_BASE_URL` | 对外访问地址（生成面试链接用） | `http://localhost:8000/` |
| `WHISPER_MODEL_GPU` / `WHISPER_MODEL_CPU` | Whisper 模型规格 | `large-v3` / `base` |
| `SCHEDULE_INTERVAL_MINUTES` | worker 轮询间隔（分钟） | `5` |
| `QUESTION_COUNT` | 每场面试题量 | `10` |

## 项目结构

```
.
├── app/
│   ├── server.py              # Flask 入口（应用工厂）
│   ├── config.py              # 集中配置（环境变量）
│   ├── database.py            # SQLite 连接与建表
│   ├── constants.py           # 状态机与业务常量
│   ├── api/                   # REST 蓝图
│   │   ├── positions.py       #   岗位管理
│   │   ├── candidates.py      #   候选人管理
│   │   └── interviews.py      #   面试管理 + 候选人端流程
│   ├── services/              # 业务服务层
│   │   ├── llm.py             #   LLM 抽象（OpenAI 兼容）
│   │   ├── asr.py             #   Whisper 语音转写
│   │   ├── resume.py          #   PDF 简历解析
│   │   ├── question_service.py#   出题逻辑
│   │   └── report_service.py  #   评估与 PDF 报告
│   ├── tasks/                 # 定时任务 worker
│   │   ├── question_worker.py
│   │   └── report_worker.py
│   └── static/                # 前端（Vue3 + Bootstrap，CDN 免构建）
├── docs/                      # 文档与示例简历（教学材料见 docs/legacy/）
├── nginx/                     # 反向代理配置（生产可选）
├── docker-compose.yml
└── LICENSE
```

## 生产部署提示

- **HTTPS**：将你的证书放入 `nginx/ssl/`（文件名 `server.pem` / `server.key`），并修改 `nginx/nginx.conf` 中的 `server_name`
- **安全**：管理后台目前面向内网 / 受信环境，公网部署建议在 nginx 层加 Basic Auth 或 IP 白名单
- **合规提醒**：候选人简历与面试录音属于个人信息，请遵守所在司法辖区的个人信息保护法律法规（如中国《个人信息保护法》、GDPR），明确告知候选人数据用途并提供删除渠道；系统删除接口会级联清理关联数据

## 贡献

欢迎 Issue 与 PR！提交前请确保通过 `pytest` 且不引入任何敏感信息（密钥、证书、真实简历）。

## License

[MIT](LICENSE)

---

<a id="english"></a>

# OpenInterview · AI-Powered Interview System

> An automated interview system powered by LLMs (GLM / OpenAI / DeepSeek via OpenAI-compatible APIs) and Whisper speech recognition. It generates tailored interview questions from resumes and job descriptions, runs voice-based online interviews, and produces structured PDF evaluation reports.

## Features

- **Smart question generation** — LLM-crafted questions with scoring rubrics based on the job description and the candidate's PDF resume
- **Online voice interviews** — candidates join via a tokenized link, answer with in-browser recording; optional text-to-speech question reading
- **Automated evaluation** — auto transcription, per-question scoring, and a rendered PDF report (technical / communication / overall scores)
- **Full recruiting management** — admin console for positions, candidates, and interviews
- **Scheduled workers** — background workers periodically process pending question generation and report tasks
- **One-command deployment** — Docker Compose

## Quick Start (Docker)

```bash
cp app/.env.example app/.env   # fill in your OPENAI_API_KEY
docker compose up --build -d
# Admin console: http://localhost:8000/static/admin.html
```

## Quick Start (Local)

```bash
cd app
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                              # fill in your API key
python server.py &                                # web API
python tasks/question_worker.py &                 # question worker
python tasks/report_worker.py                     # report worker
```

> Requires **ffmpeg** (for Whisper) and the **GTK runtime** (for WeasyPrint on Windows). See `docs/legacy/` for setup guides.

## Interview Status Machine

`0 Not started → 1 Questions ready → 2 In progress → 3 Completed → 4 Report generated`

## Configuration

All settings are managed via environment variables — see [`app/.env.example`](app/.env.example) for the full list (`OPENAI_API_KEY`, `LLM_MODEL`, `PUBLIC_BASE_URL`, `SCHEDULE_INTERVAL_MINUTES`, `QUESTION_COUNT`, ...).

## Privacy & Compliance

Resumes and interview recordings are personal data. Ensure compliance with applicable data-protection laws (e.g., PIPL, GDPR): inform candidates about data usage and provide deletion channels. Delete endpoints cascade to remove related data.

## License

[MIT](LICENSE)
