# OpenInterview · AI 智能面试系统

[中文](#中文说明) | [English](#english)

> 基于 LLM（GLM / OpenAI / DeepSeek 等兼容接口）与 Whisper 语音识别的自动化面试系统：根据候选人简历与岗位需求自动生成结构化面试题，候选人在线语音作答，系统自动转录并生成含分维度得分、优劣势分析与追问建议的 PDF 深度评估报告。

## 功能特性

- **🔐 管理端鉴权** — 口令登录（PBKDF2 存储 + 签名会话），管理接口全部受保护，登录接口限流防爆破
- **智能结构化出题** — 结合岗位 JD 与简历生成面试题：每题带能力维度（技术/项目/系统设计/行为）、难度递进、评分标准与追问建议
- **在线语音面试** — 专属链接 + token 鉴权进入，浏览器录音作答，题目语音朗读可开关，录音波形动画
- **深度自动评估** — 逐题评分引用回答原文、四维雷达数据、核心优势/短板、下一轮追问方向、录用建议，渲染为排版精良的 PDF
- **数据看板** — 岗位/候选人/面试统计、近 7 天面试量趋势
- **完整招聘管理** — 岗位、候选人、面试三合一管理后台，暗色模式，删除级联保护
- **定时自动处理** — 后台 worker 周期扫描待出题/待评估面试，单场失败不影响其他场次
- **一键部署** — Docker Compose 一条命令拉起全部服务；44 个 pytest 用例保障质量

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

1. 打开 `static/login.html` → 用初始口令登录管理后台（首次启动口令见服务日志，或由 `ADMIN_PASSWORD` 环境变量指定；**登录后请立即在「设置」中修改**）
2. **岗位管理** → 添加岗位（名称 / 要求 / 职责）
3. **候选人管理** → 添加候选人并上传 PDF 简历
4. **面试管理** → 创建面试（出题 worker 会在下个周期自动生成题目，状态变为「试题已备好」）
5. 点击 **复制链接**，发给候选人
6. 候选人打开链接 → 开始面试 → 逐题语音作答（可开启题目朗读）
7. 全部作答完毕 → 报告 worker 自动生成深度 PDF → 管理端 **下载报告**

## 运行测试

```bash
cd app
pip install pytest
ADMIN_PASSWORD=test-admin-pw pytest tests/ -v
```

测试套件自动 mock 重依赖（whisper/torch），无需 GPU 与 API Key 即可在 CI 运行。

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
- **管理员口令**：务必通过 `ADMIN_PASSWORD` 环境变量设置强口令，或首次启动后立即在后台「设置」页修改
- **会话密钥**：生产环境建议显式设置 `SECRET_KEY` 环境变量（否则自动生成并持久化在实例目录）
- **安全边界**：管理端已启用口令鉴权 + 限流；公网部署仍建议在 nginx 层叠加 Basic Auth / IP 白名单 / Fail2ban
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
