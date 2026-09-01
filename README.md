<div align="center">

# 🎙 OpenInterview

**AI 驱动的自动化面试系统 — 出题 · 语音面试 · 深度评估报告，全流程无人值守**

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions)](https://github.com/GOOD-123-CPU/OpenInterview/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000?logo=flask)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/Tests-44%20passing-brightgreen)](#运行测试)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-ff69b4.svg)](CONTRIBUTING.md)

[功能](#-功能特性) · [快速开始](#-快速开始) · [文档](#-文档) · [参与贡献](#-参与贡献) · [路线图](ROADMAP.md)

简体中文 | [English](#-english)

</div>

---

## ✨ 为什么是 OpenInterview

招聘初筛耗时长、标准不统一？OpenInterview 把「读简历 → 出题 → 面试 → 写评估」整条链路自动化：

```
 管理员建岗位/传简历          候选人打开链接语音作答           管理员下载 PDF 深度报告
        │                          │                              ▲
        ▼                          ▼                              │
  ┌──────────────┐  LLM 结构化出题  ┌──────────────┐  Whisper 转录  ┌─┴────────────┐
  │  岗位 + 简历  │ ──────────────▶ │ 浏览器录音面试 │ ────────────▶ │ LLM 深度评估   │
  └──────────────┘   维度/难度/追问  └──────────────┘   异步 worker  └──────────────┘
```

## 🌟 功能特性

| | 特性 | 说明 |
|---|------|------|
| 🔐 | **管理端鉴权** | PBKDF2 口令 + HMAC 签名会话 + 登录限流，管理接口全量保护 |
| 🧠 | **结构化出题** | 四维能力配比（技术 40%/项目 25%/设计 20%/行为 15%）、难度递进、逐题追问 |
| 🎙 | **在线语音面试** | token 链接进入 · 浏览器录音 · 题目朗读 · 波形动画 · 未到时间锁定 |
| 📊 | **深度评估报告** | 逐题引用式点评 · 雷达图 · 优势/短板 · 追问方向 · 排版精良的 PDF |
| 📈 | **数据看板** | 招聘漏斗统计 · 近 7 天趋势 · 状态分布 |
| 🔔 | **Webhook 事件** | HMAC 签名推送，对接企业微信/钉钉/Slack/n8n 自动化 |
| 🧪 | **质量保障** | 44 个 pytest 用例 · CI 矩阵 · pre-commit · ruff · detect-secrets |
| 🐳 | **一键部署** | Docker Compose 开箱即用，支持任意 OpenAI 兼容模型 |

## 🚀 快速开始

### Docker（推荐）

```bash
git clone https://github.com/GOOD-123-CPU/OpenInterview.git
cd OpenInterview

cp app/.env.example app/.env      # 填入 OPENAI_API_KEY、ADMIN_PASSWORD
docker compose up --build -d

# 打开管理后台
open http://localhost:8000/static/login.html
```

### 本地运行

```bash
cd app
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                              # 填入 OPENAI_API_KEY
python cli.py init-db

python server.py &                                # Web API
python tasks/question_worker.py &                 # 出题 worker
python tasks/report_worker.py                     # 报告 worker
```

> **系统依赖**：Whisper 需要 [ffmpeg](docs/legacy/Windows%20上安装%20FFmpeg%20指南.md)（macOS: `brew install ffmpeg`）；Windows 上 WeasyPrint 需 [GTK 运行时](docs/legacy/Windows上安装gtk.md)。

**5 分钟上手流程**：登录后台 → 建岗位 → 传候选人 PDF 简历 → 安排面试 → 等 ≤5 分钟自动出题 → 复制链接发给候选人 → 语音作答 → 下载深度 PDF 报告。

## 📖 文档

| 文档 | 内容 |
|------|------|
| [API 参考](docs/api.md) | 全部接口、鉴权、限流、Webhook 事件 |
| [架构设计](docs/architecture.md) | 分层架构、ADR 决策记录、安全模型、扩展指南 |
| [部署指南](docs/deployment.md) | Docker/裸机/systemd、HTTPS、备份、监控、故障排查 |
| [贡献指南](CONTRIBUTING.md) | 开发环境、提交规范、PR 清单 |
| [安全策略](SECURITY.md) | 漏洞上报流程、安全设计说明 |
| [更新日志](CHANGELOG.md) | 每个版本的完整变更 |

## 🏗 技术栈

`Flask 3` · `SQLite (WAL)` · `Vue 3 (CDN 免构建)` · `OpenAI 兼容 LLM（GLM/OpenAI/DeepSeek/Kimi…）` · `OpenAI Whisper` · `WeasyPrint` · `schedule` · `pytest`

**架构亮点**：提示词 YAML 版本化管理 · LLM 指数退避重试 · 请求级 request-id 追踪 · 状态机驱动的幂等 worker · 纯 Python SVG 雷达图。详见[架构文档](docs/architecture.md)。

## 🧪 运行测试

```bash
cd app
ADMIN_PASSWORD=test-admin-pw pytest tests/ -v    # 44 个用例，无需 GPU / API Key
```

## 🤝 参与贡献

欢迎一切形式的贡献！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。提交 PR 前跑一遍 `make lint test` 即可。

小改进（文档纠错、翻译、FAQ 补充）直接提 PR，无需 Issue。

## ❓ FAQ

<details>
<summary><b>支持哪些大模型？</b></summary>
任何 OpenAI 兼容接口：智谱 GLM、OpenAI、DeepSeek、Moonshot、本地 Ollama/vLLM 等。改 .env 的 OPENAI_BASE_URL 和 LLM_MODEL 即可切换。
</details>

<details>
<summary><b>必须有 GPU 吗？</b></summary>
不需要。无 GPU 自动使用 base 模型（CPU 转录 1 分钟音频约 20-40 秒，可接受）。有 GPU 自动换 large-v3，速度与精度大幅提升。
</details>

<details>
<summary><b>候选人答题数据存在哪？</b></summary>
全部在本地 SQLite 单文件中，绝不上传第三方。音频以 BLOB 存储，删除接口级联清理，另提供 <code>cli.py cleanup</code> 按天清理旧录音。
</details>

<details>
<summary><b>候选人需要注册账号吗？</b></summary>
不需要。通过 token 链接直接进入，链接即凭据，请通过私密渠道分发。
</details>

<details>
<summary><b>能对接我现有的招聘系统吗？</b></summary>
可以。完整 REST API（见 docs/api.md）+ Webhook 事件推送，或直接读写 SQLite 表。
</details>

<details>
<summary><b>管理后台暴露公网安全吗？</b></summary>
v2 起管理端已有口令鉴权+限流。仍建议：强口令、HTTPS、nginx 层叠加 IP 白名单。详见[部署指南](docs/deployment.md#首次上线检查清单)。
</details>

## ⚠️ 合规与免责

候选人简历与面试录音属于**个人信息**。使用本系统请遵守所在司法辖区的数据保护法规（中国《个人信息保护法》、GDPR 等）：明确告知候选人数据用途、提供删除渠道、做好访问控制。AI 评估结果仅供参考，最终录用决策请结合人工判断。详见 [SECURITY.md](SECURITY.md) 与[架构文档安全模型](docs/architecture.md#安全模型)。

## 📄 License

[MIT](LICENSE) © OpenInterview Contributors

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>

---

<div align="center">

<a id="-english"></a>

# 🎙 OpenInterview (English)

**Automated AI interviewing — question generation, voice interviews, and deep evaluation reports, fully unattended.**

</div>

Why OpenInterview? Screening candidates is slow and inconsistent. OpenInterview automates the whole funnel: read resume → generate structured questions → run voice interviews (Whisper transcription) → produce a deep PDF evaluation report with radar charts, strengths/weaknesses, and follow-up suggestions.

### Features

- **🔐 Admin authentication** — PBKDF2 password hashing, HMAC-signed sessions, login rate limiting
- **🧠 Structured question generation** — four competency dimensions, progressive difficulty, per-question follow-ups
- **🎙 Voice interviews** — tokenized links, in-browser recording, TTS question reading, start-time locking
- **📊 Deep evaluation reports** — transcript-grounded per-question scoring, radar chart, next-round follow-ups
- **🔔 Webhooks** — HMAC-signed events for IM bots / n8n / Zapier automation
- **🧪 Quality** — 44 pytest tests, CI matrix, pre-commit, ruff, secret scanning
- **🐳 One-command deploy** — Docker Compose; works with any OpenAI-compatible LLM

### Quick Start

```bash
git clone https://github.com/GOOD-123-CPU/OpenInterview.git && cd OpenInterview
cp app/.env.example app/.env    # fill in OPENAI_API_KEY & ADMIN_PASSWORD
docker compose up --build -d
# Admin console: http://localhost:8000/static/login.html
```

### Docs

[API Reference](docs/api.md) · [Architecture & ADRs](docs/architecture.md) · [Deployment](docs/deployment.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

### Privacy & Compliance

Resumes and interview recordings are personal data. Ensure compliance with applicable laws (PIPL, GDPR): inform candidates, provide deletion channels, and restrict access. Delete endpoints cascade automatically. AI evaluation is advisory — human judgment should make the final call.

### License

[MIT](LICENSE)
